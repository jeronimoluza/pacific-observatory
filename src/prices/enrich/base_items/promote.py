"""Statistical CANDIDATE -> GREEN promotion gate.

Groups unit-valued candidates by (base_item, pricing_basis, country) and promotes
rows within median +/- k*(1.4826*MAD) of their group. Small groups (n < MIN_GROUP_N)
are held; a basis outside the record's allowed_basis is flagged basis_conflict.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .static import (
    BASIS_CONFLICT,
    CANDIDATE_OUTLIER,
    CANDIDATE_SMALL_GROUP,
    GREEN,
)

K = 3.0
MIN_GROUP_N = 5
MAD_SCALE = 1.4826
GATE_COLS = ["promotion_status", "group_n", "group_median_usd", "band_lo", "band_hi"]


def _band(vals: np.ndarray):
    m = float(np.median(vals))
    mad = float(np.median(np.abs(vals - m)))
    scale = MAD_SCALE * mad
    if scale <= 0:
        scale = max(1e-9, 1e-6 * abs(m))
    return m, m - K * scale, m + K * scale


def promote(candidates: pd.DataFrame, allowed_basis) -> pd.DataFrame:
    df = candidates.copy().reset_index(drop=True)
    for c in GATE_COLS:
        df[c] = None if c == "promotion_status" else np.nan
    if df.empty:
        return df
    grp = df.groupby(["base_item", "pricing_basis", "country"], dropna=False)
    for (_bi, basis, _country), idx in grp.groups.items():
        sel = df.loc[idx]
        n = int(sel["unit_value_usd"].notna().sum())
        df.loc[idx, "group_n"] = n
        if allowed_basis and basis not in allowed_basis:
            df.loc[idx, "promotion_status"] = BASIS_CONFLICT
            continue
        if n < MIN_GROUP_N:
            df.loc[idx, "promotion_status"] = CANDIDATE_SMALL_GROUP
            continue
        vals = sel["unit_value_usd"].dropna().to_numpy(dtype=float)
        m, lo, hi = _band(vals)
        df.loc[idx, ["group_median_usd", "band_lo", "band_hi"]] = m, lo, hi
        uv = df.loc[idx, "unit_value_usd"]
        in_band = uv.between(lo, hi) & uv.notna()
        df.loc[idx, "promotion_status"] = np.where(in_band, GREEN, CANDIDATE_OUTLIER)
    return df


def green_only(promoted: pd.DataFrame) -> pd.DataFrame:
    return promoted[promoted["promotion_status"] == GREEN].reset_index(drop=True)
