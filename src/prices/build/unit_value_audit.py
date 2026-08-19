"""Layer-2 -- statistical unit-value outlier audit (second trust signal).

A kg of apples in one country follows a distribution. A row that sits far
outside its cell's distribution is either a bad PARSE (extract() produced a
wrong amount/basis, so unit_value_local is wrong) or a bad CLASSIFY (the head
put a non-apple into apples). Either way the row is untrustworthy for
unit-value aggregation, which is exactly what Layer-1's basis audit does not
catch (it only rejects physically-impossible (leaf, pricing_basis) pairs).

Cell = (coicop_code, country, standard_unit). The standard_unit in the key
makes every unit_value_local inside a cell unit-homogeneous and comparable
without collapsing a leaf to one modal unit, so a per-count series and a per-kg
series for the same leaf are audited independently; country pins the currency,
so no FX is needed -- we score unit_value_LOCAL. coicop_code is the deepest leaf
the live classifier assigns (the retired sub_label_id is no longer produced);
the leaf is never rolled up, so distinct products stay in distinct cells
wherever the taxonomy separates them. The caller passes group_cols; the default
below is the two-column cell for standalone use.

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

BASELINE vs SCORED (``baseline_mask``). "Normal" must be defined by rows that
measured their own quantity. A typical-mass conversion divides price by a single
per-leaf constant, so every converted row in a cell shares one denominator: a
wrong constant shifts them all together, and their spread collapses to the price
spread. Let them into the baseline and two failures follow -- a uniform mass
error becomes invisible (the conversions ARE the median they are scored
against), and where conversions outnumber measurements the real measured rows
get flagged as outliers against an estimate. Both were observed: in cells more
than 80% converted, measured rows were flagged at 36.5% against 12.2% for the
conversions, an exact inversion of the intended reading.

So the cell median, MAD and n are computed from baseline rows ONLY; non-baseline
rows are scored against that distribution but never contribute to it. A cell
with no baseline row cannot define a distribution at all, so every row in it is
flagged -- the same posture already taken for thin cells, and the honest answer
for a conversion with nothing to check it against. Passing no mask keeps the
historical behaviour exactly (every row is its own baseline).

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
    baseline_mask: pd.Series | None = None,
) -> pd.DataFrame:
    """Score every auditable row against its cell, estimated from baseline rows.

    ``baseline_mask`` selects the rows allowed to DEFINE each cell's
    distribution. Rows outside it are still scored and still flagged, they just
    do not move the median. None means every row is its own baseline, which
    reproduces the original single-population behaviour exactly.
    """
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
    if baseline_mask is None:
        base = pd.Series(True, index=df.index)
    else:
        base = baseline_mask.reindex(df.index).fillna(False).astype(bool)

    work = df.loc[auditable, group_cols].copy()
    work["_logv"] = np.log(val[auditable])
    work["_period"] = period[auditable]
    work["_base"] = base[auditable].to_numpy()

    # Temporal detrend. The per-month level is taken from baseline rows; a
    # (cell, month) with no baseline row falls back to the cell's median month
    # level, so a scored row is never detrended by its own population.
    bw = work[work["_base"]]
    month_med = bw.groupby(group_cols + ["_period"])["_logv"].median().rename("_mm")
    cell_mm = month_med.groupby(level=group_cols).median().rename("_cmm")
    work = work.join(month_med, on=group_cols + ["_period"]).join(
        cell_mm, on=group_cols
    )
    work["_resid"] = work["_logv"] - work["_mm"].fillna(work["_cmm"])

    # Cell centre, spread and support, all from baseline rows only.
    bw = work[work["_base"]].copy()
    bw["_absdev"] = (
        bw["_resid"] - bw.groupby(group_cols)["_resid"].transform("median")
    ).abs()
    stats = bw.groupby(group_cols).agg(
        _cell_med=("_resid", "median"), _mad=("_absdev", "median"), _n=("_logv", "size")
    )
    work = work.join(stats, on=group_cols)

    cell_n = work["_n"].fillna(0)
    mad = work["_mad"]
    z = pd.Series(np.nan, index=work.index)
    has_spread = mad.notna() & (mad > 0)
    z[has_spread] = (work["_resid"] - work["_cell_med"])[has_spread] / mad[has_spread]

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
