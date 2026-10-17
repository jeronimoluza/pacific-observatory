"""New per-unit orchestration: annotate (full or tail) → standardize → write outputs.

Replaces the legacy `process_unit` flow that used the EPU class with
preloaded article DataFrames. The new flow uses `source_counts.parquet`
as the per-country atomic artifact and computes aggregates by concatenating
constituent country counts on the fly (no aggregate cache).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from src.text.analysis.cache_gate import (  # noqa: F401  KEYWORDS_ROOT is read by process.py
    KEYWORDS_ROOT,
    _ensure_country_source_counts,
)
from src.text.analysis.outputs import build_outputs
from src.text.analysis.standardize import standardize_unit
from src.text.analysis.utils import load_all_groups


_logger = logging.getLogger("po.text.build")


# ── Diagnostics frozen for the summary report ────────────────────────


class UnitDiagnostics(dict):
    """Per-unit diagnostics captured during build (article counts, sources
    excluded from baseline, NaN drops, mode, runtime, status)."""

    def __init__(self):
        super().__init__()
        self["sources"] = {}
        self["mode"] = "unknown"
        self["status"] = "ok"
        self["error"] = None
        self["excluded_sources"] = []
        self["total_articles"] = 0


# ── Helpers ──────────────────────────────────────────────────────────


def _country_dir_for_path(news_csv: Path) -> Path:
    return news_csv.parent.parent


def _country_cache_dir(country_dir: Path, data_root: Path, cache_root: Path) -> Path:
    rel = country_dir.relative_to(data_root)
    return cache_root / rel


def _group_news_dirs_by_country(news_dirs: Iterable[Path]) -> dict[Path, list[Path]]:
    """Aggregate units span multiple countries — group news.csv paths by country dir."""
    grouped: dict[Path, list[Path]] = defaultdict(list)
    for fp in news_dirs:
        grouped[_country_dir_for_path(fp)].append(fp)
    return dict(grouped)


def frontier_date(per_source_max, quantile: float = 0.90):
    """Where the fleet's collection actually ends, ignoring a few fresh outliers.

    Takes the per-source newest article dates and returns a high quantile of
    them. The corpus maximum is not usable here: it is set by whichever single
    source is freshest, so probing two Taiwanese papers — 8 rows dated into
    September against August's 57,759 — was enough to move the anchor a whole
    month and wipe out the daily tail. Across 312 EAP sources, p90 and p75 both
    sat on 2026-08-27 while the maximum sat on 2026-09-04.

    Returns ``None`` for an empty input, matching ``resolve_tail_start``.
    """
    dates = sorted(d for d in per_source_max if d is not None)
    if not dates:
        return None
    idx = min(int(len(dates) * quantile), len(dates) - 1)
    return dates[idx]


def resolve_tail_start(max_real_date, today) -> str:
    """Anchor the daily tail to the corpus rather than to the wall clock.

    The tail used to start on the first of the current calendar month. That
    silently emptied it whenever collection lagged: the daily index is
    ``date_range(tail_start, max_date)``, which yields nothing once the newest
    article predates the tail. The daily rows vanish, and so do the weekly
    points the dashboard buckets from them.

    ``max_real_date`` must already exclude future-dated articles. Those are
    parse errors, and letting one drag the anchor forward would re-create the
    empty tail this exists to prevent. The anchor never runs past the current
    month, so a corpus collected up to today behaves exactly as before.
    """
    calendar_tail_start = today.replace(day=1)
    if max_real_date is None:
        return calendar_tail_start.strftime("%Y-%m-%d")
    return min(max_real_date.replace(day=1), calendar_tail_start).strftime("%Y-%m-%d")


# ── Per-unit entry point ─────────────────────────────────────────────


def process_unit_v2(
    name: str,
    level: str,
    news_dirs: list[Path],
    output_dir: Path,
    cache_dir: Path,
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
    subset_condition: str,
    source_languages: dict[str, str],
    max_parallel_sources: int,
    data_root: Path,
    cache_root: Path,
    progress_cb: Callable[[int], None] | None = None,
    file_articles: dict[Path, int] | None = None,
    daily_tail_start: str | None = None,
) -> UnitDiagnostics:
    """Process a single unit (country / subregion / region aggregate).

    ``daily_tail_start`` is resolved once per build from the corpus, so every
    unit shares one anchor and the dashboards stay comparable. Callers that
    omit it fall back to the current calendar month.

    Returns the per-unit diagnostics dict.
    """
    diagnostics = UnitDiagnostics()
    diagnostics["name"] = name
    diagnostics["level"] = level
    diagnostics["n_sources"] = len(news_dirs)

    if daily_tail_start is None:
        today = pd.Timestamp.today()
        daily_tail_start = today.replace(day=1).strftime("%Y-%m-%d")
    current_tail_start = daily_tail_start
    daily_tail_ts = pd.Timestamp(current_tail_start)

    # Subset: subset_condition is a pandas-style "date >= ... and date <= ..."
    subset_start, subset_end = _parse_subset_condition(subset_condition)

    # Country units write directly to their own cache_dir; aggregate units
    # don't have a cache — they read from constituent countries.
    if level == "country":
        df = _ensure_country_source_counts(
            country_dir=news_dirs[0].parent.parent,
            cache_dir=cache_dir,
            news_dirs=news_dirs,
            source_languages=source_languages,
            daily_tail_start=daily_tail_ts,
            subset_start=subset_start,
            subset_end=subset_end,
            max_parallel_sources=max_parallel_sources,
            diagnostics=diagnostics,
            progress_cb=progress_cb,
            file_articles=file_articles,
        )
    else:
        # Aggregate: ensure each constituent country has source_counts; auto-build.
        diagnostics["mode"] = "aggregate"
        per_country = _group_news_dirs_by_country(news_dirs)
        country_frames: list[pd.DataFrame] = []
        for country_dir, fps in per_country.items():
            country_cache = _country_cache_dir(country_dir, data_root, cache_root)
            country_langs = {str(fp): source_languages.get(str(fp), "en") for fp in fps}
            sub_diag = UnitDiagnostics()
            sub_diag["name"] = country_dir.name
            df_country = _ensure_country_source_counts(
                country_dir=country_dir,
                cache_dir=country_cache,
                news_dirs=fps,
                source_languages=country_langs,
                daily_tail_start=daily_tail_ts,
                subset_start=subset_start,
                subset_end=subset_end,
                max_parallel_sources=max_parallel_sources,
                diagnostics=sub_diag,
                progress_cb=progress_cb,
                file_articles=file_articles,
            )
            country_frames.append(df_country)
            for k, v in sub_diag["sources"].items():
                diagnostics["sources"][k] = v
            diagnostics["total_articles"] += sub_diag["total_articles"]
        df = (
            pd.concat(country_frames, ignore_index=True)
            if country_frames
            else pd.DataFrame()
        )

    if df.empty:
        diagnostics["status"] = "skipped"
        diagnostics["error"] = "no source_counts available"
        return diagnostics

    if "A_total" in df.columns:
        diagnostics["total_articles"] = int(df["A_total"].sum())

    write_unit_outputs(df, name, output_dir, cutoff_start_date, cutoff_end_date, current_tail_start)
    return diagnostics


def write_unit_outputs(
    df: pd.DataFrame,
    name: str,
    output_dir: Path,
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
    daily_tail_start: str,
) -> None:
    """Standardize a unit's source_counts and write its outputs."""
    bundle = standardize_unit(
        source_counts=df,
        cutoff_start=cutoff_start_date,
        cutoff_end=cutoff_end_date,
        daily_tail_start=daily_tail_start,
        topic_keys=list(load_all_groups("topics").keys()),
        actor_keys=list(load_all_groups("actors").keys()),
    )
    build_outputs(
        e_base=bundle["e_base"],
        topic_epus=bundle["topic_epus"],
        actor_epus=bundle["actor_epus"],
        ug_counts_all=bundle["ug_counts_all"],
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
        daily_tail_start=daily_tail_start,
        country_name=name,
        full_write=True,
        replace_from=None,
        output_dir=output_dir,
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_subset_condition(
    condition: str | None,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Extract start/end timestamps from a `date >= 'YYYY-MM-DD' and date <= '...'` string.

    Falls back to (None, None) if parsing fails — the annotator then sees no
    subset bounds and uses every available row.
    """
    if not condition:
        return None, None
    import re

    start = None
    end = None
    m = re.search(r"date\s*>=\s*'(\d{4}-\d{2}-\d{2})'", condition)
    if m:
        start = pd.Timestamp(m.group(1))
    m = re.search(r"date\s*<=\s*'(\d{4}-\d{2}-\d{2})'", condition)
    if m:
        end = pd.Timestamp(m.group(1))
    return start, end
