"""Conservative robust pruning of observed cells before fitting.

Five independent benchmarks score every cell's log USD price against a robust
centre and MAD-style scale: global product-unit, month product-unit, region
product-unit, region-month product-unit, and the cell's own series.

The combination rule is deliberately reluctant. A cell is dropped only when it
is severe on the global benchmark, or extreme under two benchmarks that are not
measuring the same thing. On William's 358,710-cell input this removes 872 cells
-- 0.24% -- and that number is the cheapest check that this port is faithful.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

REASON_COLS = (
    "flag_global_severe",
    "flag_global_extreme",
    "flag_month_extreme",
    "flag_region_extreme",
    "flag_region_month_extreme",
    "flag_series_spike",
)

_ROBUST_Z_COLS = (
    "global_product_unit_robust_z",
    "month_product_unit_robust_z",
    "region_product_unit_robust_z",
    "region_month_product_unit_robust_z",
    "series_robust_z",
)


def add_group_score(df, group_col, prefix, min_count, scale_floor):
    """Robust z of ``y`` within one grouping.

    The scale is ``1.4826 * MAD`` floored at ``scale_floor``, and is set to NaN
    where the group is smaller than ``min_count`` -- an undersampled group has
    no opinion, so it must abstain rather than flag.
    """
    out = df
    grouped = out.groupby(group_col, observed=True, sort=False)["y"]
    center = grouped.transform("median")
    count = grouped.transform("size").astype(float)
    absdev = (out["y"] - center).abs()
    mad = absdev.groupby(out[group_col], observed=True, sort=False).transform("median")
    scale = np.maximum(1.4826 * mad.to_numpy(dtype=float), scale_floor)
    scale = np.where(count.to_numpy(dtype=float) >= min_count, scale, np.nan)
    diff = out["y"].to_numpy(dtype=float) - center.to_numpy(dtype=float)
    out[f"{prefix}_center"] = center
    out[f"{prefix}_count"] = count
    out[f"{prefix}_abs_log_ratio"] = np.abs(diff)
    out[f"{prefix}_signed_log_ratio"] = diff
    out[f"{prefix}_robust_z"] = np.abs(diff) / scale
    return out


def build_outlier_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for group_col, prefix, min_count, scale_floor in config.PRUNE_BENCHMARKS:
        out = add_group_score(out, group_col, prefix, min_count, scale_floor)

    def _hit(prefix, min_count, z, ratio):
        return (
            (out[f"{prefix}_count"] >= min_count)
            & (out[f"{prefix}_robust_z"] >= z)
            & (out[f"{prefix}_abs_log_ratio"] >= ratio)
        )

    global_extreme = _hit("global_product_unit", 80, config.GLOBAL_EXTREME_Z, config.GLOBAL_EXTREME_RATIO)
    global_severe = _hit("global_product_unit", 80, config.GLOBAL_SEVERE_Z, config.GLOBAL_SEVERE_RATIO)
    month_extreme = _hit("month_product_unit", 20, config.MONTH_EXTREME_Z, config.MONTH_EXTREME_RATIO)
    region_extreme = _hit("region_product_unit", 30, config.REGION_EXTREME_Z, config.REGION_EXTREME_RATIO)
    region_month_extreme = _hit(
        "region_month_product_unit", 10, config.REGION_MONTH_EXTREME_Z, config.REGION_MONTH_EXTREME_RATIO
    )
    # A series spike must be corroborated: a series that is simply expensive
    # everywhere would otherwise flag its own every observation.
    series_spike = _hit("series", 8, config.SERIES_SPIKE_Z, config.SERIES_SPIKE_RATIO) & (
        (out["global_product_unit_robust_z"] >= config.SERIES_SPIKE_CORROBORATING_Z)
        | (out["month_product_unit_robust_z"] >= config.SERIES_SPIKE_CORROBORATING_Z)
    )

    out["flag_global_extreme"] = global_extreme
    out["flag_global_severe"] = global_severe
    out["flag_month_extreme"] = month_extreme
    out["flag_region_extreme"] = region_extreme
    out["flag_region_month_extreme"] = region_month_extreme
    out["flag_series_spike"] = series_spike
    out["outlier_score"] = out[list(_ROBUST_Z_COLS)].max(axis=1, skipna=True)

    out["is_suspicious_value"] = (
        global_severe
        | (global_extreme & (month_extreme | region_extreme | region_month_extreme))
        | (month_extreme & (region_extreme | region_month_extreme))
        | series_spike
    )

    out["outlier_reason"] = ""
    for col in REASON_COLS:
        label = col.removeprefix("flag_")
        hit = out[col].fillna(False)
        out.loc[hit, "outlier_reason"] = out.loc[hit, "outlier_reason"].map(
            lambda value, lab=label: f"{value};{lab}".strip(";")
        )
    return out


def prune(df: pd.DataFrame):
    """Returns (kept, flagged, summary)."""
    flagged_frame = build_outlier_flags(df)
    suspicious = flagged_frame["is_suspicious_value"].fillna(False)
    kept = flagged_frame.loc[~suspicious].reset_index(drop=True)
    flagged = flagged_frame.loc[suspicious].reset_index(drop=True)

    by_country = (
        flagged_frame.assign(_f=suspicious.astype(int))
        .groupby("country", observed=True)["_f"]
        .agg(["sum", "size"])
    )
    by_country["share"] = by_country["sum"] / by_country["size"]

    summary = {
        "pruning_version": config.PRUNING_VERSION,
        "input_rows": int(len(flagged_frame)),
        "flagged_rows": int(suspicious.sum()),
        "pruned_rows": int(len(kept)),
        "flagged_share": float(suspicious.mean()) if len(flagged_frame) else 0.0,
        # Counted among FLAGGED cells only -- a reason that fires on a cell the
        # combination rule then spares is not a pruning reason. Will's
        # `outlier_reason_counts.csv` header says `flagged_cells` for exactly
        # this reason, and counting frame-wide inflates every count.
        "reason_counts": {
            col.removeprefix("flag_"): int(flagged_frame.loc[suspicious, col].fillna(False).sum())
            for col in REASON_COLS
        },
        "worst_country_share": float(by_country["share"].max()) if len(by_country) else 0.0,
        "countries_over_limit": sorted(
            by_country.index[by_country["share"] > config.DRIFT_MAX_COUNTRY_PRUNED_SHARE].tolist()
        ),
    }
    return kept, flagged, summary
