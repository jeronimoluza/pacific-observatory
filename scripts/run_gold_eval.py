"""Run enrich pipeline against the 50-row hand-labeled gold set and report per-field accuracy.

Distinct from `scripts/run_eval.py`, which runs the 500-row distributional probe
(no labels, no accuracy). This one inner-joins eval_set.csv ↔ eval_labels_gold.csv
on eval_id, enriches the 50 rows, and prints predicted-vs-gold scores.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prices.enrich import config
from prices.enrich.tier_b import cache
from prices.enrich.stages.enrich import _enrich_async, _structured_input
from prices.enrich.versioning import (
    PROMPT_BYTES_HASH,
    PROMPT_SEMVER,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
    cache_key,
)

GOLD_CSV = Path("src/prices/enrich/static/eval_labels_gold.csv")
EVAL_CSV = Path("src/prices/enrich/static/eval_set.csv")

FIELDS_STR = [
    "pricing_basis",
    "standard_unit",
    "coicop_code",
    "sub_label_id",
    "state",
]
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
    """For count/multiplier: blank in gold means 'default 1' (no multipack/multiplier),
    which the model emits as explicit '1'. Treat them as equal."""
    s = _norm_num(v)
    return "1" if s == "" else s


def _norm_coicop(v) -> str:
    s = _norm(v)
    # Normalize trailing ".0" suffix and any zero-padding mismatch
    return s


def main() -> None:
    eval_df = pd.read_csv(EVAL_CSV, dtype=str, keep_default_na=False)
    gold_df = pd.read_csv(GOLD_CSV, dtype=str, keep_default_na=False)

    # Drop noisy reference cols from eval_set that would collide with gold + pred names.
    eval_df = eval_df.drop(
        columns=[
            c
            for c in [
                "coicop_code",
                "coicop_title",
                "standard_unit",
                "amount",
                "units",
                "has_promotion",
            ]
            if c in eval_df.columns
        ]
    )
    # Suffix gold label cols upfront so the post-enrich merge doesn't collide.
    gold_df = gold_df.rename(
        columns={c: f"{c}_gold" for c in gold_df.columns if c != "eval_id"}
    )

    joined_in = eval_df.merge(gold_df, on="eval_id", how="inner")
    print(f"Joined {len(joined_in)} gold rows for enrichment", flush=True)

    # Run enrich (writes into cache parquet)
    asyncio.run(_enrich_async(joined_in))

    cached = cache.read_cache()
    if cached.empty:
        raise SystemExit(
            "Cache is empty after enrich — check API key / failures parquet"
        )

    joined_in["cache_key"] = joined_in.apply(
        lambda r: cache_key(_structured_input(r)), axis=1
    )
    pred = cached.drop(
        columns=[
            c
            for c in ["product_name_original", "country", "currency"]
            if c in cached.columns
        ]
    )
    pred = pred.rename(
        columns={c: f"{c}_pred" for c in pred.columns if c != "cache_key"}
    )
    df = joined_in.merge(pred, on="cache_key", how="left")

    missing = (
        df["coicop_code_pred"].isna().sum()
        if "coicop_code_pred" in df.columns
        else len(df)
    )
    print(f"Predictions found for {len(df) - missing}/{len(df)} rows", flush=True)

    # Per-field accuracy
    print("\n=== Per-field accuracy (gold N=50) ===")
    report_rows = []
    for f in FIELDS_STR + FIELDS_NUM + FIELDS_BOOL:
        gold_col = f"{f}_gold" if f"{f}_gold" in df.columns else f
        pred_col = f"{f}_pred" if f"{f}_pred" in df.columns else f
        if gold_col not in df.columns or pred_col not in df.columns:
            continue
        normer = (
            _norm_bool
            if f in FIELDS_BOOL
            else _norm_count_or_mult
            if f in {"count", "multiplier"}
            else _norm_num
            if f in FIELDS_NUM
            else _norm_coicop
            if f == "coicop_code"
            else _norm
        )
        g = df[gold_col].apply(normer)
        p = df[pred_col].apply(normer)
        ok = (g == p).sum()
        report_rows.append((f, ok, len(df), f"{ok/len(df):.0%}"))
        print(f"  {f:18s} {ok:>3d}/{len(df):>3d}  {ok/len(df):.0%}")

    # Coicop + sub_label_id joint accuracy
    g_code = (
        df["coicop_code_gold"].apply(_norm_coicop)
        if "coicop_code_gold" in df.columns
        else df["coicop_code"].apply(_norm_coicop)
    )
    p_code = (
        df["coicop_code_pred"].apply(_norm_coicop)
        if "coicop_code_pred" in df.columns
        else df["coicop_code"].apply(_norm_coicop)
    )
    g_sub = (
        df["sub_label_id_gold"].apply(_norm)
        if "sub_label_id_gold" in df.columns
        else df["sub_label_id"].apply(_norm)
    )
    p_sub = (
        df["sub_label_id_pred"].apply(_norm)
        if "sub_label_id_pred" in df.columns
        else df["sub_label_id"].apply(_norm)
    )
    joint = ((g_code == p_code) & (g_sub == p_sub)).sum()
    print(
        f"  {'coicop+sub_label':18s} {joint:>3d}/{len(df):>3d}  {joint/len(df):.0%}  (joint)"
    )

    # Mismatches dump (top 30, focused on coicop+sub_label)
    print("\n=== Top mismatches (coicop_code / sub_label_id) ===")
    mism = df[(g_code != p_code) | (g_sub != p_sub)].copy()
    mism["g_code"] = g_code
    mism["p_code"] = p_code
    mism["g_sub"] = g_sub
    mism["p_sub"] = p_sub
    for _, r in mism.head(30).iterrows():
        name = str(r.get("product_name_original", ""))[:60]
        print(
            f"  {r['eval_id']}  {r.get('country','?'):20s}  "
            f"{r['g_code']}/{r['g_sub']:<20s} → {r['p_code']}/{r['p_sub']:<20s}  "
            f"| {name}"
        )

    # Write per-row dump for inspection
    out_path = Path("data/prices/_enrich/gold_eval_predictions.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    keep_cols = [
        "eval_id",
        "eval_bucket",
        "country",
        "product_name_original",
        "coicop_code_gold",
        "coicop_code_pred",
        "sub_label_id_gold",
        "sub_label_id_pred",
        "pricing_basis_gold",
        "pricing_basis_pred",
        "amount_value_gold",
        "amount_value_pred",
        "standard_unit_gold",
        "standard_unit_pred",
        "count_gold",
        "count_pred",
        "multiplier_gold",
        "multiplier_pred",
        "is_promotion_gold",
        "is_promotion_pred",
        "is_bundle_gold",
        "is_bundle_pred",
        "is_multipack_gold",
        "is_multipack_pred",
        "state_gold",
        "state_pred",
        "confidence_pred",
        "label_notes_gold",
    ]
    df[[c for c in keep_cols if c in df.columns]].to_csv(out_path, index=False)
    print(f"\nPer-row dump → {out_path}")

    # Summary line for capture
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_semver": PROMPT_SEMVER,
        "prompt_bytes_hash": PROMPT_BYTES_HASH,
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "model": config.MODEL_NAME,
        "n_gold": len(df),
        "n_predicted": int(len(df) - missing),
        "scores": {f: int(ok) for f, ok, _, _ in report_rows},
        "coicop_plus_sub_ok": int(joint),
    }
    print("\nSUMMARY=" + json.dumps(summary))


if __name__ == "__main__":
    main()
