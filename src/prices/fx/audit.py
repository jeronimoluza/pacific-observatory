"""Detect FX rates that are wrong by orders of magnitude.

The motivating defect: MNT sat at ~3,595 per USD, dropped to 0.608 for
exactly 22 days (2025-10-25 .. 2025-11-15), then returned to ~3,573. One
observation landed in that window and published at $3,980.45. ``qa_fx``
returned ``True`` throughout, because it only asks whether an ``fx_rate`` is
non-null -- never whether it is plausible.

**Why the obvious detector does not work.** A "far from the currency's
lifetime median" test fires on 22 of the 149 currencies -- SDG, ARS, SSP,
SYP, ZWL, TRY, LYD, VES, UZS, SRD, LBP, NGN, BYN, KPW, AOA, ETB, IRR, UAH,
ZMW, EGP, MNT, GHS -- because those currencies really did move orders of
magnitude. Distance from a median cannot separate a merge artefact from
hyperinflation.

**What does work is the shape of the move, tested at block level:**

    a real redenomination or hyperinflation STEPS AND STAYS;
    contamination STEPS AND RETURNS.

So the test runs in two stages. First a robust local level -- a *centered*
rolling median over a window several times longer than any plausible
contamination block -- nominates candidate rows. Centering matters: a
trailing-only window shorter than the block gets contaminated by the block
itself and the block hides from its own detector. Then candidates are grouped
into date-contiguous blocks, and a block survives only if the level
immediately *before* it and immediately *after* it agree with each other
while both disagree with the block. Across a real devaluation the two sides
disagree, so it is dropped.

**Known blind spots, stated rather than papered over:**

* A block at the very start or end of a currency's series has only one side,
  so the return cannot be confirmed and the block is not reported.
* A block longer than roughly a third of :data:`DEFAULT_WINDOW` contaminates
  its own centered median and will be missed.
* A wrong rate within :data:`DEFAULT_FACTOR` of the true one is invisible to
  this test entirely. It catches order-of-magnitude errors, which is the
  class that produced a $3,980 juice box -- not subtle drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: Days used for the centered robust level. Must be several times longer than
#: any contamination block you expect to catch -- the MNT block was 22 days.
DEFAULT_WINDOW = 181
#: How far off the local level a rate must sit to become a candidate. 3x is
#: far above any real one-day float move.
DEFAULT_FACTOR = 3.0
#: How closely the levels either side of a block must agree for the move to
#: count as "returned" rather than "stayed".
DEFAULT_RETURN_TOL = 1.5
#: Observations either side of a block used to measure the return.
DEFAULT_EDGE = 10


def _candidate_mask(
    cache: pd.DataFrame, window: int, factor: float
) -> pd.Series:
    """Rows sitting more than ``factor`` off a centered rolling median."""
    flags = pd.Series(False, index=cache.index)
    for _, group in cache.groupby("currency", sort=False):
        ordered = group.sort_values("date")
        rate = pd.to_numeric(ordered["rate_usd_to_local"], errors="coerce")
        positive = rate.where(rate > 0)
        level = positive.rolling(window, center=True, min_periods=5).median()
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = positive / level
        suspect = (
            level.notna() & ((ratio > factor) | (ratio < 1.0 / factor))
        ).fillna(False)
        flags.loc[ordered.index] = suspect.to_numpy()
    return flags


def find_contaminated_blocks(
    cache: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
    factor: float = DEFAULT_FACTOR,
    return_tol: float = DEFAULT_RETURN_TOL,
    edge: int = DEFAULT_EDGE,
    max_gap_days: int = 3,
) -> pd.DataFrame:
    """Date-contiguous blocks where a stable currency stepped and returned.

    Clean edges around date-bounded garbage is a merge signature, so the block
    -- not the individual row -- is the unit worth reporting.

    Columns: ``currency, start, end, days, rate_min, rate_max,
    baseline_before, baseline_after, ratio, returned``. Only rows with
    ``returned`` true are included; see the module docstring for why.
    """
    empty = pd.DataFrame(
        columns=[
            "currency", "start", "end", "days", "rate_min", "rate_max",
            "baseline_before", "baseline_after", "ratio", "returned",
        ]
    )
    if cache.empty:
        return empty

    candidates = cache[_candidate_mask(cache, window, factor)]
    if candidates.empty:
        return empty

    rows = []
    for currency, group in candidates.groupby("currency", sort=True):
        ordered = group.sort_values("date")
        gaps = ordered["date"].diff().dt.days.fillna(0)
        block_id = (gaps > max_gap_days).cumsum()
        full = cache[cache["currency"] == currency].sort_values("date")
        for _, block in ordered.groupby(block_id):
            start, end = block["date"].min(), block["date"].max()
            before = full[full["date"] < start]["rate_usd_to_local"].tail(edge)
            after = full[full["date"] > end]["rate_usd_to_local"].head(edge)
            if before.empty or after.empty:
                # One-sided: cannot confirm a return, so cannot distinguish
                # this from a devaluation at the edge of coverage.
                continue
            baseline_before = float(before.median())
            baseline_after = float(after.median())
            block_rate = float(block["rate_usd_to_local"].median())
            if not (baseline_before > 0 and baseline_after > 0 and block_rate > 0):
                continue

            side_ratio = max(baseline_before, baseline_after) / min(
                baseline_before, baseline_after
            )
            returned = side_ratio <= return_tol
            baseline = (baseline_before + baseline_after) / 2.0
            ratio = baseline / block_rate
            if not returned or max(ratio, 1.0 / ratio) < factor:
                continue

            rows.append(
                {
                    "currency": currency,
                    "start": start,
                    "end": end,
                    "days": int((end - start).days) + 1,
                    "rate_min": float(block["rate_usd_to_local"].min()),
                    "rate_max": float(block["rate_usd_to_local"].max()),
                    "baseline_before": baseline_before,
                    "baseline_after": baseline_after,
                    "ratio": ratio,
                    "returned": True,
                }
            )
    if not rows:
        return empty
    return pd.DataFrame(rows).sort_values(["currency", "start"]).reset_index(drop=True)


def flag_rate_outliers(
    cache: pd.DataFrame,
    window: int = DEFAULT_WINDOW,
    factor: float = DEFAULT_FACTOR,
    return_tol: float = DEFAULT_RETURN_TOL,
    edge: int = DEFAULT_EDGE,
) -> pd.Series:
    """Boolean mask over ``cache``: row belongs to a confirmed bad block.

    Aligned to ``cache.index``. This is the row-level view of
    :func:`find_contaminated_blocks`, so it inherits the same blind spots and,
    importantly, the same refusal to flag genuine devaluations.
    """
    flags = pd.Series(False, index=cache.index)
    blocks = find_contaminated_blocks(
        cache, window=window, factor=factor, return_tol=return_tol, edge=edge
    )
    for block in blocks.itertuples(index=False):
        flags |= (
            cache["currency"].eq(block.currency)
            & cache["date"].ge(block.start)
            & cache["date"].le(block.end)
        )
    return flags


def suspect_keys(
    cache: pd.DataFrame, **kwargs
) -> set[tuple[str, pd.Timestamp]]:
    """``(currency, date)`` pairs a build should refuse to convert at.

    This is the build-time form of the audit: computed once per build from the
    cache, then joined against observation rows so ``qa_fx`` can fail a row
    whose rate is implausible instead of merely absent.
    """
    if cache.empty:
        return set()
    suspect = cache[flag_rate_outliers(cache, **kwargs)]
    return set(zip(suspect["currency"], suspect["date"]))
