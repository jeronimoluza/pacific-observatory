"""Audit enrichment quality. Read-only.

Three detectors:
  D1 price-per-unit z-score within (country, sub_label_id), MAD-based, N>=10,
     restricted to pricing_basis in {mass, volume, count} where unit math is meaningful.
  D2 pricing_basis compatibility: flag rows whose pricing_basis differs from the
     modal pricing_basis of their sub_label_id (when N_subgroup >= 20).
  D4 low-confidence resolved: state == 'resolved' AND confidence < 0.6.

Outputs:
  outputs/prices/audit/flagged_rows.csv    — one row per flag with detector label
  outputs/prices/audit/flagged_summary.md  — counts + worst offenders
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich.stages.merge import compute_unit_value  # noqa: E402

CACHE = REPO_ROOT / "data/prices/_enrich/cache/enrichments.parquet"
PI = REPO_ROOT / "data/prices/_enrich/products_input.parquet"
OUT_DIR = REPO_ROOT / "outputs/prices/audit"

MIN_GROUP_N_Z = 10
MIN_GROUP_N_BASIS = 20
Z_THRESHOLD = 3.5
LOW_CONF = 0.6
UNIT_BASES = {"mass", "volume", "count"}


def _unit_price(row) -> float:
    # Delegate to the canonical compute_unit_value in merge.py so audit math
    # matches what publish actually sees — including the multipack-collapse
    # workaround for legacy double-counted rows (c==m>1 → c=1, m=1).
    v = compute_unit_value(
        row["price"],
        row["pricing_basis"],
        row.get("amount_value"),
        row.get("count"),
        row.get("multiplier"),
    )
    return np.nan if v is None else v


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cache = pd.read_parquet(CACHE)
    pi = pd.read_parquet(PI)[["product_name_original", "country", "currency", "price"]]
    df = cache.merge(
        pi, on=["product_name_original", "country", "currency"], how="left"
    )
    df = df[df["price"].notna()].copy()
    print(f"joined: {len(df):,} of {len(cache):,} cache rows have a price")

    # D1: price-per-unit z within (country, currency, sub_label_id).
    # Currency must be in the group key — same-country mixed-currency groups
    # otherwise flag every minority-currency row as an outlier.
    # `_other` is a wildcard bucket — its intra-group variance is expected, skip.
    mask_unit = (
        df["pricing_basis"].isin(UNIT_BASES)
        & df["state"].eq("resolved")
        & df["sub_label_id"].notna()
        & df["sub_label_id"].ne("_other")
    )
    u = df[mask_unit].copy()
    u["unit_price"] = u.apply(_unit_price, axis=1)
    u = u[u["unit_price"].notna() & (u["unit_price"] > 0)]
    u["log_up"] = np.log(u["unit_price"])
    grp = u.groupby(["country", "currency", "sub_label_id"])["log_up"]
    med = grp.transform("median")
    mad = grp.transform(lambda s: (s - s.median()).abs().median())
    n = grp.transform("size")
    rob_z = (u["log_up"] - med) / (mad.replace(0, np.nan) * 1.4826)
    u["robust_z"] = rob_z
    u["group_n"] = n
    d1 = u[
        (u["group_n"] >= MIN_GROUP_N_Z) & (u["robust_z"].abs() >= Z_THRESHOLD)
    ].copy()
    d1["detector"] = "D1_unit_price_zscore"

    # D2: pricing_basis vs modal pricing_basis per sub_label_id (skip `_other`).
    df_d2 = df[df["sub_label_id"].notna() & df["sub_label_id"].ne("_other")]
    sub_counts = (
        df_d2.groupby(["sub_label_id", "pricing_basis"]).size().reset_index(name="n")
    )
    totals = sub_counts.groupby("sub_label_id")["n"].sum().rename("total").reset_index()
    sub_counts = sub_counts.merge(totals, on="sub_label_id")
    modal = (
        sub_counts.sort_values(["sub_label_id", "n"], ascending=[True, False])
        .groupby("sub_label_id")
        .head(1)
        .rename(columns={"pricing_basis": "modal_basis"})
    )
    eligible = modal[modal["total"] >= MIN_GROUP_N_BASIS][
        ["sub_label_id", "modal_basis"]
    ]
    d2 = df_d2.merge(eligible, on="sub_label_id", how="inner")
    d2 = d2[d2["pricing_basis"] != d2["modal_basis"]].copy()
    d2["detector"] = "D2_basis_mismatch"

    # D4: low-confidence resolved
    d4 = df[(df["state"] == "resolved") & (df["confidence"] < LOW_CONF)].copy()
    d4["detector"] = "D4_low_confidence"

    keep_cols = [
        "detector",
        "product_name_original",
        "country",
        "currency",
        "price",
        "coicop_code",
        "sub_label_id",
        "pricing_basis",
        "amount_value",
        "standard_unit",
        "count",
        "multiplier",
        "confidence",
        "state",
        "cache_key",
    ]
    for d in (d1, d2, d4):
        for c in keep_cols:
            if c not in d.columns:
                d[c] = np.nan
    extras = {"D1_unit_price_zscore": ["unit_price", "robust_z", "group_n"]}
    out = pd.concat(
        [
            d1[keep_cols + extras["D1_unit_price_zscore"]],
            d2[keep_cols + ["modal_basis"]],
            d4[keep_cols],
        ],
        ignore_index=True,
    )

    flagged_csv = OUT_DIR / "flagged_rows.csv"
    out.to_csv(flagged_csv, index=False)
    print(f"wrote {flagged_csv}  ({len(out):,} rows)")

    summary = []
    summary.append(f"# Enrichment audit ({len(df):,} priced cache rows)\n")
    summary.append("## Detector counts\n")
    summary.append(
        f"- D1 unit-price z-score (|z|>={Z_THRESHOLD}, N>={MIN_GROUP_N_Z}): **{len(d1):,}**"
    )
    summary.append(
        f"- D2 basis mismatch (sub_label N>={MIN_GROUP_N_BASIS}): **{len(d2):,}**"
    )
    summary.append(f"- D4 low-confidence resolved (<{LOW_CONF}): **{len(d4):,}**\n")

    if len(d1):
        summary.append("## D1 worst offenders (top 15 by |z|)")
        top = d1.reindex(d1["robust_z"].abs().sort_values(ascending=False).index).head(
            15
        )
        summary.append(
            top[
                [
                    "country",
                    "sub_label_id",
                    "product_name_original",
                    "price",
                    "unit_price",
                    "robust_z",
                    "group_n",
                ]
            ].to_markdown(index=False)
        )
        summary.append("")
        summary.append("## D1 hottest groups (top 10 by flag count)")
        hot = (
            d1.groupby(["country", "sub_label_id"])
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        summary.append(hot.to_frame("flagged").to_markdown())
        summary.append("")

    if len(d2):
        summary.append("## D2 sub_labels with most basis-mismatches (top 10)")
        hot = (
            d2.groupby(["sub_label_id", "modal_basis", "pricing_basis"])
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        summary.append(hot.to_frame("n").to_markdown())
        summary.append("")

    if len(d4):
        summary.append("## D4 sub_labels with most low-conf resolved (top 10)")
        hot = d4.groupby(["sub_label_id"]).size().sort_values(ascending=False).head(10)
        summary.append(hot.to_frame("n").to_markdown())
        summary.append("")

    # Drift report: distinct prompt_bytes_hash within each prompt_semver.
    # A semver should map to ONE bytes hash. >1 means the prompt was edited
    # without bumping semver — silent cache drift.
    if "prompt_semver" in df.columns and "prompt_bytes_hash" in df.columns:
        drift = (
            df.dropna(subset=["prompt_semver"])
            .groupby("prompt_semver")["prompt_bytes_hash"]
            .agg(distinct_hashes="nunique", n_rows="count")
            .reset_index()
        )
        summary.append("## Prompt drift (distinct bytes-hash per semver)")
        summary.append(drift.to_markdown(index=False))
        leaky = drift[drift["distinct_hashes"] > 1]
        if len(leaky):
            summary.append("")
            summary.append(
                "**Note:** semver(s) above with >1 distinct bytes-hash either had "
                "rows carried forward across a semver bump (via drop_flagged_from_cache.py) "
                "or had the prompt edited mid-semver. Carry-forward is expected; "
                "mid-semver edits without a bump are silent drift — bump PROMPT_SEMVER if so."
            )
        summary.append("")

    summary_md = OUT_DIR / "flagged_summary.md"
    summary_md.write_text("\n".join(summary))
    print(f"wrote {summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
