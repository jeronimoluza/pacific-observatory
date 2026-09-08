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
  - robust score in WILL'S UNITS: robust_sd = 1.4826*MAD, the consistent sigma
    estimator for a normal population, and uv_robust_z = residual / robust_sd.
    The threshold is |robust_z| > k with k=5.0, which is Will's stated rule of
    2026-08-31 verbatim. MAD==0 (no spread) -> abstain, never flag:
    precision-first, we under-cover rather than mis-reject.

    This column used to divide by the RAW MAD and default to k=3.0. Those are
    not the same rule: 3.0 raw MADs is |robust_z| = 2.02, so the shipped audit
    was 2.5x TIGHTER than the spec it claimed to implement, and the number in
    the column could not be read against the threshold Will wrote down.
    Correcting the scale and the constant together is one change, not two --
    changing either alone silently moves the operating point.
  - thin cells (pooled n < min_n) get their trust withheld (flag), never
    scored -- too few rows to estimate a distribution. min_n is 3, not 5: three
    baseline rows is the least that yields a non-degenerate MAD, and at 5 the
    corpus withheld 348,545 rows it had never actually judged.

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

Non-destructive: adds five columns, drops nothing. The consumable deliverable
is the rows where Layer-1 trust_level=="high" AND Layer-2 trust_uv=="high";
everything else is quarantined for human triage, never auto-fabricated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NEW_COLS = ["uv_robust_z", "uv_cell_n", "uv_outlier", "uv_thin", "trust_uv"]

# MAD -> sigma for a normal population. Without it `uv_robust_z` is in raw-MAD
# units and cannot be compared to the |z| > 5 Will specified.
MAD_TO_SIGMA = 1.4826

# Months on either side of a row's own month that may lend it SUPPORT. Will put
# the survey period in the cell key, which is right for the comparison -- a row
# must be judged against prices from its own month, never against a different
# month's price level. But it slices support so finely that most cells fall
# under min_n and lose trust for lack of evidence rather than for any defect:
# 1,003,316 rows, 67.7% of everything flagged, on the measured build.
#
# So the period splits the COMPARISON and a +/-1 month window pools the COUNT.
# Nothing about what a row is scored against changes, so no inter-period price
# movement can register as an outlier; a cell that is thin in March alone but
# well-observed in February and April becomes judgeable. A 6-month window was
# considered and 3 months chosen, recovering 198,418 rows against a projected
# 287,831.
UV_SUPPORT_WINDOW = 1


def _pooled_support(
    n_by_period: pd.Series, cell_cols: list[str], window: int
) -> pd.Series:
    """Support per (cell, month), widened to the months within `window` of it.

    Joined by month ARITHMETIC, not by row position: a cell observed in January
    and June has adjacent rows in this table but four empty months between them,
    and a positional roll would pool them as if they were neighbours. Shifting
    the ordinal and merging keeps a gap a gap.
    """
    s = n_by_period.rename("_n_period").reset_index()
    s["_ord"] = pd.PeriodIndex(s["_period"], freq="M").astype("int64")
    total = np.zeros(len(s), dtype="int64")
    for off in range(-window, window + 1):
        other = s[cell_cols + ["_ord", "_n_period"]].copy()
        other["_ord"] = other["_ord"] + off
        merged = s[cell_cols + ["_ord"]].merge(
            other, on=cell_cols + ["_ord"], how="left"
        )
        total += merged["_n_period"].fillna(0).to_numpy().astype("int64")
    s["_n"] = total
    return s.set_index(cell_cols + ["_period"])["_n"]


def flag_uv_outliers(
    df: pd.DataFrame,
    *,
    group_cols: tuple[str, ...] = ("coicop_code", "country"),
    period_col: str = "observation_date",
    value_col: str = "unit_value_local",
    k: float = 5.0,
    min_n: int = 3,
    support_window: int = UV_SUPPORT_WINDOW,
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
    df["uv_thin"] = False
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
    key = group_cols + ["_period"]

    # Cell centre, spread and support, all from baseline rows only.
    bw = work[work["_base"]].copy()
    # Centre and spread within (cell, MONTH) -- Will put the survey period in the
    # cell key, so a row is compared only against prices from its own month.
    bw["_absdev"] = (
        bw["_resid"] - bw.groupby(key)["_resid"].transform("median")
    ).abs()
    stats = bw.groupby(key).agg(
        _cell_med=("_resid", "median"),
        _mad=("_absdev", "median"),
        _n_period=("_logv", "size"),
    )
    stats["_n"] = _pooled_support(stats["_n_period"], group_cols, support_window)
    work = work.join(stats, on=key)

    cell_n = work["_n"].fillna(0)
    mad = work["_mad"]
    z = pd.Series(np.nan, index=work.index)
    has_spread = mad.notna() & (mad > 0)
    z[has_spread] = (work["_resid"] - work["_cell_med"])[has_spread] / (
        MAD_TO_SIGMA * mad[has_spread]
    )

    thin = cell_n < min_n
    z[thin.values] = np.nan
    outlier = (z.abs() > k) & (~thin)
    trust_uv = np.where(outlier.values | thin.values, "flag", "high")

    idx = df.index[auditable]
    df.loc[idx, "uv_cell_n"] = cell_n.astype(int).to_numpy()
    df.loc[idx, "uv_robust_z"] = z.to_numpy()
    df.loc[idx, "uv_outlier"] = outlier.to_numpy()
    # Emitted so a reader can tell the two "flag" verdicts apart. `thin` already
    # decides trust_uv above, but it was never written out, so qa.py's
    # `df.get("uv_thin", ...)` fell through to its all-False default and every
    # thin row was reported as review_uv_outlier -- "we judged this and it
    # failed" -- when the truth is that its cell had too few baseline rows to
    # judge it at all. Not a gate: it changes the REASON, never shippability.
    df.loc[idx, "uv_thin"] = thin.to_numpy()
    df.loc[idx, "trust_uv"] = trust_uv
    return df
