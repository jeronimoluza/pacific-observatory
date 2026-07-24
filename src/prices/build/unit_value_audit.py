"""Layer-2 -- statistical unit-value outlier audit (second trust signal).

A kg of apples in one country follows a distribution. A row that sits far
outside its cell's distribution is either a bad PARSE (extract() produced a
wrong amount/basis, so unit_value_local is wrong) or a bad CLASSIFY (the head
put a non-apple into apples). Either way the row is untrustworthy for
unit-value aggregation, which is exactly what Layer-1's basis audit does not
catch (it only rejects physically-impossible (leaf, pricing_basis) pairs).

Cell = (coicop_code, country). `_canonicalize_units` in aggregate.py already
collapses each coicop_code leaf to its modal standard_unit, so every
unit_value_local inside a cell is unit-homogeneous and comparable; country
pins the currency, so no FX is needed -- we score unit_value_LOCAL. coicop_code
is the deepest leaf the live classifier assigns (the retired sub_label_id is no
longer produced); the leaf is never rolled up, so distinct products stay in
distinct cells wherever the taxonomy separates them.

Method (one code path for snapshot and observations):
  - log space (prices are multiplicative / right-skewed)
  - temporal detrend: within each cell, per year_month median of the raw value
    is the baseline; a row's residual is log(value) - log(its month median).
    Pooling residuals across months keeps n high while removing
    inflation/seasonality, so a legitimately drifting cell is not flagged.
    Snapshot degenerates naturally: all rows share one period, so the month
    median equals the cell median and this is plain cross-sectional MAD.
  - robust score: median +/- k*MAD on the pooled residuals (k=3.0), matching
    the classify-base-item convention. MAD==0 (no spread) -> abstain, never
    flag: precision-first, we under-cover rather than mis-reject.
  - thin cells (pooled n < min_n) get their trust withheld (flag), never
    scored -- too few rows to estimate a distribution.

Non-destructive: adds four columns, drops nothing. The consumable deliverable
is the rows where Layer-1 trust_level=="high" AND Layer-2 trust_uv=="high";
everything else is quarantined for human triage, never auto-fabricated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NEW_COLS = ["uv_robust_z", "uv_cell_n", "uv_outlier", "trust_uv"]


def flag_uv_outliers(
    df: pd.DataFrame,
    *,
    group_cols: tuple[str, ...] = ("coicop_code", "country"),
    period_col: str = "observation_date",
    value_col: str = "unit_value_local",
    k: float = 3.0,
    min_n: int = 5,
) -> pd.DataFrame:
    df = df.copy()
    df["uv_robust_z"] = np.nan
    df["uv_cell_n"] = 0
    df["uv_outlier"] = False
    df["trust_uv"] = "high"
    if df.empty:
        return df

    group_cols = list(group_cols)
    val = pd.to_numeric(df[value_col], errors="coerce")
    auditable = val.notna() & (val > 0)
    if not auditable.any():
        return df

    period = (
        pd.to_datetime(df[period_col], errors="coerce").dt.to_period("M").astype(str)
    )

    work = df.loc[auditable, group_cols].copy()
    work["_logv"] = np.log(val[auditable])
    work["_period"] = period[auditable]

    month_med = work.groupby(group_cols + ["_period"])["_logv"].transform("median")
    work["_resid"] = work["_logv"] - month_med

    g = work.groupby(group_cols)
    cell_med = g["_resid"].transform("median")
    work["_absdev"] = (work["_resid"] - cell_med).abs()
    mad = g["_absdev"].transform("median")
    cell_n = g["_logv"].transform("size")

    z = pd.Series(np.nan, index=work.index)
    has_spread = mad > 0
    z[has_spread] = (work["_resid"] - cell_med)[has_spread] / mad[has_spread]

    thin = cell_n < min_n
    z[thin.values] = np.nan
    outlier = (z.abs() > k) & (~thin)
    trust_uv = np.where(outlier.values | thin.values, "flag", "high")

    idx = df.index[auditable]
    df.loc[idx, "uv_cell_n"] = cell_n.astype(int).to_numpy()
    df.loc[idx, "uv_robust_z"] = z.to_numpy()
    df.loc[idx, "uv_outlier"] = outlier.to_numpy()
    df.loc[idx, "trust_uv"] = trust_uv
    return df
