"""Stream a corpus delta into a country's counts state, without re-reading its corpus.

The delta is a signed-off merge plan (``<pending>/<plan_id>/``, text.panel.signoff):
per source, the exact news.csv rows appended to the corpus, already URL-deduplicated
against it. Every column of source_counts is a count or a sum (annotate._grouped_for_frame),
so annotating only the delta rows and adding them to the state cells they fall in equals a
full re-annotation of the merged file. A late article lands in its own (older) month or
tail day, which reopens that cell. A plan applies once per country (``deltas.json``).

Falls back to a full partition run when the state cannot take a delta: no state yet,
keyword files changed, or a source the state has never seen (its whole corpus file is
annotated then, not just the delta).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from src.text.analysis import annotate, source_counts
from src.text.analysis.cache_gate import (
    KEYWORDS_ROOT,
    _dedup_source_counts,
    _languages_used,
)
from src.text.analysis.utils import LANGUAGE_ALIASES
from src.text.source_keys import source_key

APPLIED_FILE = "deltas.json"


class NeedsFull(RuntimeError):
    pass


def plan_sources(plan_dir: Path) -> dict[str, list[tuple[str, Path, Path]]]:
    """country -> [(region, delta news.csv, corpus news.csv)] of a plan's appended news rows."""
    out: dict[str, list[tuple[str, Path, Path]]] = {}
    with open(plan_dir / "PLAN.tsv", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["file"] != "news.csv" or int(row["new_rows"] or 0) == 0:
                continue
            delta = plan_dir / row["region"] / row["key"] / "news.csv"
            out.setdefault(row["key"].split("/")[1], []).append(
                (row["region"], delta, Path(row["target"]))
            )
    return out


def event_weeks(delta_csv: Path, end: pd.Timestamp) -> set[str]:
    dates = pd.to_datetime(
        pd.read_csv(delta_csv, usecols=["date"])["date"],
        format="mixed",
        errors="coerce",
    )
    dates = dates[dates.notna() & (dates <= end)]
    return {d.strftime("%G-W%V") for d in dates}


def _add(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Cell-wise sum of two source_counts frames (keys source_key, ym)."""
    both = pd.concat([a, b], ignore_index=True)
    metrics = [c for c in both.columns if c not in ("source_key", "ym")]
    both[metrics] = both[metrics].fillna(0)
    out = both.groupby(["source_key", "ym"], as_index=False, sort=False)[metrics].sum()
    for c in metrics:
        out[c] = out[c].astype(a[c].dtype if c in a.columns else b[c].dtype)
    return out[list(a.columns) + [c for c in out.columns if c not in a.columns]]


def apply_delta(
    cache_dir: Path,
    items: list[tuple[Path, Path, str]],
    tail_start: str,
    end: str,
    plan_id: str,
) -> dict:
    """Add ``items`` [(delta news.csv, corpus news.csv, language)] to the state in ``cache_dir``."""
    df, params = source_counts.read_source_counts(cache_dir)
    if df is None:
        raise NeedsFull("no state")
    applied_path = cache_dir / APPLIED_FILE
    applied = json.loads(applied_path.read_text()) if applied_path.exists() else {}
    if plan_id in applied:
        return {"skipped": f"{plan_id} already applied", **applied[plan_id]}
    state_langs = set(params.keyword_hashes.get("epu.json", {}))
    if params.keyword_hashes != source_counts.keyword_hash_bundle(
        KEYWORDS_ROOT, state_langs
    ):
        raise NeedsFull("keyword files changed")
    if not _languages_used({str(d): lang for d, _, lang in items}) <= state_langs:
        raise NeedsFull("a delta language the state has no keyword hashes for")
    tail = pd.Timestamp(tail_start)
    subset = (pd.Timestamp("2015-01-01"), pd.Timestamp(end))
    state = _dedup_source_counts(df, tail)
    tails = dict(params.tails)
    weeks: set[str] = set()
    rows = 0
    for delta_csv, corpus_csv, lang in items:
        sk = source_key(corpus_csv)
        if sk not in params.source_set:
            raise NeedsFull(f"new source {sk}")
        bundle = annotate.KeywordBundle.for_language(LANGUAGE_ALIASES.get(lang, lang))
        frame, diag = annotate.annotate_source(delta_csv, sk, bundle, tail, *subset)
        state = _add(state, _dedup_source_counts(frame, tail))
        old = tails.get(sk, {})
        last = [
            d
            for d in (
                old.get("last_date"),
                diag["max_date"] and diag["max_date"].strftime("%Y-%m-%d"),
            )
            if d
        ]
        tails[sk] = {
            "last_date": max(last) if last else None,
            "n_rows": int(old.get("n_rows", 0)) + int(diag["n_total"]),
        }
        weeks |= event_weeks(delta_csv, subset[1])
        rows += int(diag["n_total"])
    state = _dedup_source_counts(state, tail)
    params.tails = tails
    source_counts.write_source_counts(cache_dir, state, params)
    applied[plan_id] = {"rows": rows, "sources": len(items), "weeks": sorted(weeks)}
    applied_path.write_text(json.dumps(applied, indent=2))
    return applied[plan_id]
