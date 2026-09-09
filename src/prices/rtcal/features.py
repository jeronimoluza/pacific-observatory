"""Support counts and the gate's feature frame.

The gate never sees a price. It sees only how much evidence stood behind the
prediction and how much the component predictors disagreed -- which is why it
generalises to cells whose true value nobody has ever observed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .predict import ALL_COMPONENTS, grouped_stat, map_series

SUPPORT_KEYS = {
    "series_train_count": "series_id",
    "country_product_train_count": "country_product_id",
    "product_unit_train_count": "product_unit_id",
    "product_period_train_count": "product_unit_period_id",
    "country_period_train_count": "country_period_id",
    "period_train_count": "period",
    "country_train_count": "country",
    "coicop_train_count": "coicop_code",
}

NEAREST_GAP_CAP = 999.0


def support_features(train, val) -> pd.DataFrame:
    features = pd.DataFrame(index=val.index)
    for out_col, key in SUPPORT_KEYS.items():
        counts = grouped_stat(train, key, stat="count")
        features[out_col] = (
            pd.Series(map_series(val[key], counts), index=val.index).fillna(0).astype(int)
        )
    return features


def nearest_gap_features(train, val) -> pd.Series:
    """Months to the closest same-series training observation, either direction.

    ``inf`` where the series has no training rows at all -- capped downstream at
    999 so the gate reads "as far away as it gets" rather than choking.
    """
    out = pd.Series(np.inf, index=val.index, dtype=float)
    periods_by_series = {
        series: group["period_index"].to_numpy(dtype=int)
        for series, group in train[["series_id", "period_index"]]
        .sort_values(["series_id", "period_index"])
        .groupby("series_id", sort=False)
    }
    for series, sub in val.groupby("series_id", sort=False):
        periods = periods_by_series.get(series)
        if periods is None or len(periods) == 0:
            continue
        target = sub["period_index"].to_numpy(dtype=int)
        idx = np.searchsorted(periods, target)
        prev_gap = np.full(len(target), np.inf)
        next_gap = np.full(len(target), np.inf)
        has_prev = idx > 0
        has_next = idx < len(periods)
        prev_gap[has_prev] = target[has_prev] - periods[idx[has_prev] - 1]
        next_gap[has_next] = periods[idx[has_next]] - target[has_next]
        out.loc[sub.index] = np.minimum(prev_gap, next_gap)
    return out


def build_gate_frame(val, preds, stats, candidate, support):
    """Assemble the per-candidate audit frame the gate trains and scores on."""
    frame = pd.DataFrame(index=val.index)
    for col in SUPPORT_KEYS:
        frame[col] = support[col].to_numpy()
    frame["nearest_series_gap"] = support["nearest_series_gap"].to_numpy()
    frame["period_index"] = val["period_index"].to_numpy(dtype=float)

    candidate_pred = preds[candidate]
    frame["candidate_prediction"] = candidate_pred
    frame["candidate_model_sd"] = stats.get(f"{candidate}_sd", np.full(len(val), np.nan))
    frame["candidate_model_range"] = stats.get(f"{candidate}_range", np.full(len(val), np.nan))
    frame["ensemble_structural_sd"] = stats["ensemble_structural_sd"]
    frame["ensemble_structural_range"] = stats["ensemble_structural_range"]

    for name in ALL_COMPONENTS:
        if name in preds:
            frame[f"absdiff_{name}"] = np.abs(candidate_pred - preds[name])
    return frame


GATE_BASE_FEATURES = [f"log1p_{col}" for col in SUPPORT_KEYS] + [
    "nearest_series_gap_capped",
    "period_index",
    "candidate_model_sd",
    "candidate_model_range",
    "ensemble_structural_sd",
    "ensemble_structural_range",
]


def gate_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Feature matrix for the HGB gate.

    Missing dispersion reads as 999, not as 0: an absent disagreement signal is
    ignorance, and encoding it as agreement would make the gate confident about
    exactly the cells it knows least about.
    """
    x = pd.DataFrame(index=df.index)
    for col in SUPPORT_KEYS:
        x[f"log1p_{col}"] = np.log1p(df[col].fillna(0).to_numpy(dtype=float))
    nearest = df["nearest_series_gap"].replace([np.inf, -np.inf], np.nan).fillna(NEAREST_GAP_CAP)
    x["nearest_series_gap_capped"] = np.minimum(nearest.to_numpy(dtype=float), NEAREST_GAP_CAP)
    x["period_index"] = df["period_index"].to_numpy(dtype=float)
    for col in ("candidate_model_sd", "candidate_model_range", "ensemble_structural_sd", "ensemble_structural_range"):
        x[col] = df[col].fillna(NEAREST_GAP_CAP).to_numpy(dtype=float)
    for col in df.columns:
        if col.startswith("absdiff_"):
            x[col] = df[col].fillna(NEAREST_GAP_CAP).to_numpy(dtype=float)
    return x
