"""Report-only gold-set regression check.

Reads the current enrichments cache and the hand-labelled gold set
(`data/prices/_enrich/gold_eval_predictions.csv`, 100 rows). Joins on
(product_name_original, country), picks the latest cache row per gold
tuple, and scores per-field + joint (coicop+sub_label) accuracy.

If a baseline file exists, prints deltas vs baseline. If not, writes the
current scores as the baseline. Either way, exits 0 — this is a
report-only signal for the operator, not a CI gate. Pair it with an
enrich run by chaining: `po prices enrich && python scripts/check_gold_regression.py`.

Flags:
  --update-baseline   overwrite the baseline JSON with current scores
  --strict-pp N       echo a WARN line (still exit 0) on any field
                      whose joint or per-field accuracy drops by >=N
                      percentage points vs baseline (default 5)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich.tier_b import cache as enrich_cache  # noqa: E402
from prices.enrich.versioning import (  # noqa: E402
    PROMPT_SEMVER,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
)

GOLD_CSV = REPO_ROOT / "data/prices/_enrich/gold_eval_predictions.csv"
BASELINE_JSON = REPO_ROOT / "data/prices/_enrich/gold_baseline.json"
HISTORY_JSONL = REPO_ROOT / "data/prices/_enrich/gold_history.jsonl"

FIELDS_STR = ["pricing_basis", "standard_unit", "coicop_code", "sub_label_id", "state"]
FIELDS_BOOL = ["is_promotion", "is_bundle", "is_multipack"]
FIELDS_NUM = ["amount_value", "count", "multiplier"]


def _norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() in {"nan", "none", "<na>"}:
        return ""
    return s


def _norm_bool(v) -> str:
    s = _norm(v).lower()
    if s in {"true", "1", "yes"}:
        return "true"
    if s in {"false", "0", "no", ""}:
        return "false"
    return s


def _norm_num(v) -> str:
    s = _norm(v)
    if s == "":
        return ""
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return f"{f:.6g}"
    except ValueError:
        return s


def _norm_count_or_mult(v) -> str:
    s = _norm_num(v)
    return "1" if s == "" else s


def _join_latest_cache_to_gold(gold: pd.DataFrame, cache: pd.DataFrame) -> pd.DataFrame:
    """Take the most recent cache row per (product_name_original, country).

    Gold has no currency column, so this collapses across currencies — the
    semantic of trust we want is "does the current cache contain a correct
    prediction for this product." Last-write-wins matches what the build
    stage sees after dedup.
    """
    if "created_at" in cache.columns:
        cache = cache.sort_values("created_at")
    cache = cache.drop_duplicates(
        subset=["product_name_original", "country"], keep="last"
    )
    keep_cols = ["product_name_original", "country"]
    for f in FIELDS_STR + FIELDS_NUM + FIELDS_BOOL:
        if f in cache.columns:
            keep_cols.append(f)
    if "confidence" in cache.columns:
        keep_cols.append("confidence")
    return gold.merge(
        cache[keep_cols].rename(
            columns={
                c: f"{c}_now"
                for c in keep_cols
                if c not in {"product_name_original", "country"}
            }
        ),
        on=["product_name_original", "country"],
        how="left",
    )


def _score(df: pd.DataFrame) -> dict:
    """Per-field accuracy of *_now vs *_gold over the joined rows."""
    n_total = len(df)
    n_pred = (
        int(df["coicop_code_now"].notna().sum())
        if "coicop_code_now" in df.columns
        else 0
    )
    scores: dict[str, int] = {}
    for f in FIELDS_STR + FIELDS_NUM + FIELDS_BOOL:
        gold_col = f"{f}_gold"
        pred_col = f"{f}_now"
        if gold_col not in df.columns or pred_col not in df.columns:
            continue
        normer = (
            _norm_bool
            if f in FIELDS_BOOL
            else _norm_count_or_mult
            if f in {"count", "multiplier"}
            else _norm_num
            if f in FIELDS_NUM
            else _norm
        )
        scores[f] = int(
            (df[gold_col].apply(normer) == df[pred_col].apply(normer)).sum()
        )

    g_code = df["coicop_code_gold"].apply(_norm)
    p_code = df["coicop_code_now"].apply(_norm)
    g_sub = df["sub_label_id_gold"].apply(_norm)
    p_sub = df["sub_label_id_now"].apply(_norm)
    joint = int(((g_code == p_code) & (g_sub == p_sub)).sum())
    return {"n_total": n_total, "n_pred": n_pred, "fields": scores, "joint": joint}


def _pp(n: int, total: int) -> float:
    return 0.0 if total == 0 else round(100.0 * n / total, 1)


def _print_report(curr: dict, baseline: dict | None, strict_pp: float) -> int:
    n = curr["n_total"]
    print(f"\n=== Gold regression (N={n}, joined to current cache) ===")
    print(f"  predictions found: {curr['n_pred']}/{n}")
    warns = 0
    rows = [("coicop+sub_label", curr["joint"])] + list(curr["fields"].items())
    for f, ok in rows:
        curr_pct = _pp(ok, n)
        if baseline is None:
            print(f"  {f:20s} {ok:>3d}/{n:>3d}  {curr_pct:>5.1f}%")
            continue
        base_ok = (
            baseline.get("joint")
            if f == "coicop+sub_label"
            else baseline.get("fields", {}).get(f)
        )
        if base_ok is None:
            print(f"  {f:20s} {ok:>3d}/{n:>3d}  {curr_pct:>5.1f}%   (no baseline)")
            continue
        base_pct = _pp(base_ok, baseline.get("n_total", n))
        delta = curr_pct - base_pct
        tag = ""
        if -delta >= strict_pp:
            tag = f"  WARN: -{-delta:.1f}pp vs baseline ({base_pct:.1f}%)"
            warns += 1
        elif delta != 0:
            tag = f"  ({'+' if delta > 0 else ''}{delta:.1f}pp vs {base_pct:.1f}%)"
        print(f"  {f:20s} {ok:>3d}/{n:>3d}  {curr_pct:>5.1f}%{tag}")
    print()
    return warns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite gold_baseline.json with the current scores.",
    )
    parser.add_argument(
        "--strict-pp",
        type=float,
        default=5.0,
        help="Flag (WARN, no nonzero exit) any field that drops >=N pp vs baseline.",
    )
    parser.add_argument(
        "--min-coverage",
        type=int,
        default=90,
        help="Skip baseline auto-write when joined coverage < N rows. "
        "Prevents a low-coverage run from poisoning the baseline.",
    )
    args = parser.parse_args()

    if not GOLD_CSV.exists():
        print(f"gold set not found: {GOLD_CSV}", file=sys.stderr)
        return 0
    gold = pd.read_csv(GOLD_CSV)
    cache = enrich_cache.read_cache()
    if cache.empty:
        print("cache is empty; skipping regression check", file=sys.stderr)
        return 0

    joined = _join_latest_cache_to_gold(gold, cache)
    curr = _score(joined)

    baseline = json.loads(BASELINE_JSON.read_text()) if BASELINE_JSON.exists() else None
    warns = _print_report(curr, baseline, args.strict_pp)

    history_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_semver": PROMPT_SEMVER,
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        **curr,
    }
    HISTORY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_JSONL.open("a") as fh:
        fh.write(json.dumps(history_entry) + "\n")

    want_baseline_write = args.update_baseline or baseline is None
    if want_baseline_write and curr["n_pred"] < args.min_coverage:
        print(
            f"coverage {curr['n_pred']}/{curr['n_total']} below --min-coverage "
            f"({args.min_coverage}); skipping baseline write. "
            "Re-enrich the gold rows (scripts/run_gold_eval.py) before pinning."
        )
    elif want_baseline_write:
        BASELINE_JSON.write_text(json.dumps(history_entry, indent=2))
        print(f"baseline written → {BASELINE_JSON}")

    if warns:
        print(
            f"{warns} field(s) regressed by >={args.strict_pp}pp — review before publish."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
