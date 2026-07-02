"""One loop iteration for a single base_item.

grep deduped data -> mine source boilerplate -> cascade -> validate GREEN ->
emit the validation_runs artifact + REVIEW report-back. Stops at the artifact;
the human reviews it before the GREEN rows are appended to
outputs/prices/{region}_prices.csv (append_region()).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import spacy

from prices.enrich.config import PRODUCTS_INPUT_PARQUET, REPO_ROOT

from . import mine, store, validate
from .cascade import classify_names
from .phrase_index import food_phrase_index

OUTPUTS_DIR = REPO_ROOT / "outputs" / "prices"

RATIO_MAX = 2.0
MOVED_MIN = 0.05


def loop_status(n_candidate, n_green, moved_fraction):
    if n_green and n_candidate <= RATIO_MAX * n_green:
        return {"stop": True, "reason": "ratio"}
    if moved_fraction < MOVED_MIN:
        return {"stop": True, "reason": "convergence"}
    return {"stop": False, "reason": "continue"}


def _basis_conflict_report(promoted, rec):
    bad = promoted[promoted["promotion_status"] == "basis_conflict"]
    if bad.empty:
        return ""
    lines = [
        f"base_item allowed_basis={sorted(rec.get('allowed_basis') or [])} "
        f"plausible_basis={sorted(str(x) for x in (rec.get('plausible_basis') or []))}"
    ]
    for basis, n in bad["pricing_basis"].value_counts().items():
        lines.append(
            f"  {n} rows priced by '{basis}' (plausible but not allowed) "
            f"-> widen allowed_basis to promote, or improve parsing"
        )
    return "\n".join(lines)


def _moved_fraction(base_item, current):
    """Fraction of rows whose decision differs from the latest prior run folder."""
    import glob

    prev = sorted(glob.glob(str(validate.VALIDATION_RUNS_DIR / f"{base_item}_*")))
    prev = [p for p in prev if Path(p) != Path(current)]
    if not prev:
        return 1.0
    try:
        pd.read_csv(Path(prev[-1]) / "candidates.csv")
    except Exception:
        return 1.0
    return 1.0  # first cut: prior-run diff refined post-MVP; conservative -> continue


def _grep_slice(base_item_rec: dict, region: str | None) -> pd.DataFrame:
    df = pd.read_parquet(PRODUCTS_INPUT_PARQUET)
    if region and "region" in df.columns:
        df = df[df["region"] == region]
    aliases = sorted(base_item_rec["tokens"], key=len, reverse=True)
    pat = re.compile(r"\b(?:" + "|".join(re.escape(a) for a in aliases) + r")\b", re.I)
    mask = df["product_name_original"].astype(str).str.contains(pat)
    return df[mask].reset_index(drop=True).copy()


def full_corpus(base_items_df):
    """Union of the deduped-cache slices for every base_item token set.

    Greps PRODUCTS_INPUT_PARQUET once per base_item record (via _grep_slice),
    concatenates, and de-duplicates on product_name_original. Returns a frame
    with at least product_name_original and lang columns.
    """
    names = sorted(set(base_items_df["base_item"].astype(str)))
    frames = []
    for base_item in names:
        try:
            rec = store.load_record(base_item)
        except KeyError:
            continue
        sl = _grep_slice(rec, None)
        if sl.empty:
            continue
        if "product_name_original" not in sl.columns and "name" in sl.columns:
            sl = sl.rename(columns={"name": "product_name_original"})
        frames.append(sl)
    if not frames:
        return pd.DataFrame(columns=["product_name_original", "lang"])
    out = pd.concat(frames, ignore_index=True)
    if "lang" not in out.columns:
        out["lang"] = None
    return out.drop_duplicates(subset=["product_name_original"]).reset_index(drop=True)


def run_iteration(base_item: str, region: str | None = None, nlp=None) -> dict:
    ts = datetime.now(timezone.utc)
    rec = store.load_record(base_item)
    sl = _grep_slice(rec, region)
    if sl.empty:
        return {"base_item": base_item, "n": 0, "note": "no matching rows"}

    # mine per-source boilerplate from the sources present (full catalog if
    # available), then load the union scoped to those sources.
    boiler = set()
    if "source" in sl.columns:
        srcs = set(sl["source"].dropna().astype(str))
        if os.environ.get("BASE_ITEMS_SKIP_MINE") not in ("1", "true", "True"):
            full = pd.read_parquet(PRODUCTS_INPUT_PARQUET)
            if "source" in full.columns:
                full = full[full["source"].astype(str).isin(srcs)]
                mine.mine_source_boilerplate(full)
        boiler = store.load_boilerplate(srcs)

    if nlp is None:
        nlp = spacy.load("en_core_web_sm", disable=["ner"])
    sub_idx = food_phrase_index()
    form_lex, neg_lex = store.load_form_lexicon(), store.load_neg_lexicon()

    langs = sl["lang"] if "lang" in sl.columns else [None] * len(sl)
    got = classify_names(
        sl["product_name_original"],
        langs,
        rec,
        nlp,
        boiler,
        sub_idx,
        form_lex,
        neg_lex,
    )
    sl["decision"] = [g[0] for g in got]
    sl["reason"] = [g[1] for g in got]
    sl["pricing_basis"] = [g[2] for g in got]

    dist = sl["decision"].value_counts().to_dict()

    green = sl[sl["decision"] == "CANDIDATE"].copy()
    if "observation_date" not in green.columns:
        green["observation_date"] = pd.NaT

    from . import promote as P

    art, demoted = validate.validate_green(green, rec, base_item, ts)
    promoted = P.promote(art, rec.get("allowed_basis"))
    run_dir = validate.write_run(promoted, sl, base_item, ts)

    n_green = (
        int((promoted["promotion_status"] == "green").sum())
        if not promoted.empty
        else 0
    )
    n_candidate = len(promoted)
    moved = _moved_fraction(base_item, run_dir)
    status = loop_status(n_candidate, n_green, moved)

    report = _basis_conflict_report(promoted, rec)
    if report:
        (Path(run_dir) / "basis_conflict.txt").write_text(report, encoding="utf-8")

    candidates, cross = mine.review_residue(sl)

    return {
        "base_item": base_item,
        "region": region,
        "n": len(sl),
        "distribution": dist,
        "green_validated": len(art),
        "green_demoted": len(demoted),
        "run_dir": run_dir,
        "review_brand_candidates": candidates.head(30).to_dict("records"),
        "review_cross_base_items": cross.to_dict("records"),
        "promotion": promoted["promotion_status"].value_counts().to_dict()
        if not promoted.empty and "promotion_status" in promoted.columns
        else {},
        "n_green": n_green,
        "loop_status": status,
        "basis_conflict": report,
    }


def append_region(run_dir: str, region: str) -> str:
    """Append a reviewed run's green.csv to outputs/prices/{region}_prices.csv."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUTS_DIR / f"{region}_prices.csv"
    new = pd.read_csv(Path(run_dir) / "green.csv")
    if out.exists():
        new = pd.concat([pd.read_csv(out), new], ignore_index=True)
    new.to_csv(out, index=False)
    return str(out)
