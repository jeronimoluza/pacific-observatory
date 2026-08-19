"""Consumable deliverables: trusted row-level observations + monthly summary.

Two curated outputs derived from a finalized build frame (one that already
carries the Layer-1 ``trust_level``, Layer-2 ``trust_uv``, FX, and QA columns):

  1. trusted_observations -- the row-level deliverable. Every row with
     ``qa_status == "trusted"``: exact observation timestamp, local + USD unit
     value, the structural fields that produced it, and provenance. Nothing is
     fabricated; rows that failed any gate are simply absent (they remain in the
     build parquet under their review_* status for triage).

  2. unit_value_summary -- the aggregated deliverable at monthly grain
     ``(period, coicop_code, country, standard_unit)``. standard_unit is kept in
     the key (never collapsed to a modal unit) so eggs-by-dozen and eggs-by-kg
     survive as two distinct trusted series. Medians are computed over
     trusted-only rows; ``n_total`` reports the full cell for context, and
     ``uv_log_mad`` is the within-cell dispersion -- the "same distribution per
     pricing_basis, per country" tightness check, made explicit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SUMMARY_KEYS = ["period", "coicop_code", "country", "standard_unit"]

# A summary cell needs at least this many trusted rows before its median is
# considered usable; mirrors the Layer-2 min_n so thin cells are reported but
# flagged rather than silently trusted.
MIN_CELL_N = 5

TRUSTED_OBS_COLS = [
    "observation_date",
    "country",
    "coicop_code",
    "pricing_basis",
    "standard_unit",
    "amount_value",
    "count",
    "multiplier",
    "product_name",
    "product_name_original",
    "source",
    "price_local",
    "currency",
    "unit_value_local",
    "unit_value_usd",
    "confidence",
    "trust_level",
    "trust_uv",
    "uv_robust_z",
    "qa_status",
    "mass_source",
]


def trusted_observations(df: pd.DataFrame) -> pd.DataFrame:
    """Row-level deliverable: the qa_status=='trusted' rows with provenance."""
    if df.empty or "qa_status" not in df.columns:
        return df.iloc[0:0].copy()
    out = df[df["qa_status"] == "trusted"].copy()
    keep = [c for c in TRUSTED_OBS_COLS if c in out.columns]
    return out[keep].reset_index(drop=True)


def _log_mad(values: pd.Series) -> float:
    v = pd.to_numeric(values, errors="coerce")
    v = v[v > 0]
    if len(v) < 2:
        return np.nan
    logv = np.log(v)
    return float((logv - logv.median()).abs().median())


def build_unit_value_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly (period, leaf, country, unit) summary over trusted rows.

    n_total counts every row in the cell (any qa_status); the medians and
    dispersion use trusted rows only. A cell with fewer than MIN_CELL_N trusted
    rows is kept but marked ``cell_status == "thin"``.
    """
    if df.empty:
        return pd.DataFrame(columns=SUMMARY_KEYS)
    work = df.copy()
    work["period"] = (
        pd.to_datetime(work["observation_date"], errors="coerce")
        .dt.to_period("M")
        .astype(str)
    )

    total = work.groupby(SUMMARY_KEYS, dropna=False).size().rename("n_total")

    trusted = work[work["qa_status"] == "trusted"]
    if trusted.empty:
        summary = total.reset_index()
        summary["n_trusted"] = 0
        for col in (
            "median_unit_value_local",
            "median_unit_value_usd",
            "uv_log_mad",
            "confidence_median",
        ):
            summary[col] = np.nan
        summary["cell_status"] = "thin"
        return summary

    grp = trusted.groupby(SUMMARY_KEYS, dropna=False)
    agg = grp.agg(
        n_trusted=("unit_value_local", "size"),
        median_unit_value_local=("unit_value_local", "median"),
        median_unit_value_usd=("unit_value_usd", "median"),
        confidence_median=("confidence", "median"),
    )
    agg["uv_log_mad"] = grp["unit_value_local"].apply(_log_mad)

    summary = agg.join(total, how="right").reset_index()
    summary["n_trusted"] = summary["n_trusted"].fillna(0).astype(int)
    summary["cell_status"] = np.where(
        summary["n_trusted"] >= MIN_CELL_N, "usable", "thin"
    )
    return summary
