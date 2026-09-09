"""Which cells RT-CAL tries to fill, and why each one is missing.

The target universe is the union of two things:

* **Span expansion.** For every series that has been observed at all, every
  month from its first observation to its last, plus every month from its last
  observation forward to the newest period in the corpus. This is what makes a
  curve continuous, and it is most of the opportunity -- 459,583 interior gaps
  against 358,710 observed cells.
* **Attempted-but-unusable cells.** Rows present in the summary that failed to
  become observed (`n_trusted == 0` or no USD value). Mostly already inside a
  span; the remainder are series that have never once resolved.

Classification matters more than it looks, because it selects both the predictor
and the threshold. A cell misfiled as a normal gap gets released on an 80%-target
rule that was never validated for it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import frames

# Support below this counts as "thin" when deciding whether a normal gap is
# country-shaped or product-shaped. Matches the bar the validation subsets use.
THIN_SUPPORT = 10

MISSINGNESS_TYPES = (
    "new_country_product_unit_series",
    "future_or_latest_month_gap",
    "country_month_gap",
    "product_month_gap",
    "normal_gap_mixed",
)


def build_targets(cells: pd.DataFrame, observed: pd.DataFrame) -> pd.DataFrame:
    """Target coordinates, deduplicated, with observed cells excluded.

    ``observed`` must be the POST-PRUNE training frame: a cell whose observation
    was pruned as implausible is a cell we no longer believe, so it becomes a
    target rather than staying a fact.
    """
    period_index = frames.period_index_map(cells["period"])
    index_period = {v: k for k, v in period_index.items()}
    last_index = max(period_index.values())

    obs_idx = observed["period"].map(period_index).to_numpy(dtype=int)
    span = (
        pd.DataFrame(
            {
                "country": observed["country"].to_numpy(),
                "coicop_code": observed["coicop_code"].to_numpy(),
                "standard_unit": observed["standard_unit"].to_numpy(),
                "pi": obs_idx,
            }
        )
        .groupby(["country", "coicop_code", "standard_unit"], observed=True)["pi"]
        .agg(["min", "max"])
        .reset_index()
    )

    rows = []
    for country, code, unit, lo, hi in span.itertuples(index=False, name=None):
        # interior gaps plus everything from the last observation to today
        rows.append((country, code, unit, np.arange(int(lo), last_index + 1, dtype=int)))

    frame = pd.DataFrame(
        {
            "country": np.repeat([r[0] for r in rows], [len(r[3]) for r in rows]),
            "coicop_code": np.repeat([r[1] for r in rows], [len(r[3]) for r in rows]),
            "standard_unit": np.repeat([r[2] for r in rows], [len(r[3]) for r in rows]),
            "period_index": np.concatenate([r[3] for r in rows]),
        }
    )
    frame["period"] = frame["period_index"].map(index_period)

    attempted = cells[["country", "coicop_code", "standard_unit", "period", "period_index"]]
    universe = pd.concat([frame, attempted], ignore_index=True)
    universe = universe.drop_duplicates(["country", "coicop_code", "standard_unit", "period"])

    observed_keys = set(
        map(tuple, observed[["country", "coicop_code", "standard_unit", "period"]].to_numpy())
    )
    keys = list(map(tuple, universe[["country", "coicop_code", "standard_unit", "period"]].to_numpy()))
    universe = universe.loc[[k not in observed_keys for k in keys]].reset_index(drop=True)
    return frames.add_core_ids(universe)


def classify_missingness(targets: pd.DataFrame, observed: pd.DataFrame) -> pd.Series:
    """Assign each target the gap type that selects its predictor and threshold."""
    series_counts = observed.groupby("series_id", observed=True).size()
    series_last = observed.groupby("series_id", observed=True)["period_index"].max()
    country_period = observed.groupby("country_period_id", observed=True).size()
    product_period = observed.groupby("product_unit_period_id", observed=True).size()

    n_series = targets["series_id"].map(series_counts).fillna(0).to_numpy(dtype=float)
    last_seen = targets["series_id"].map(series_last).to_numpy(dtype=float)
    n_country_period = targets["country_period_id"].map(country_period).fillna(0).to_numpy(dtype=float)
    n_product_period = targets["product_unit_period_id"].map(product_period).fillna(0).to_numpy(dtype=float)
    target_index = targets["period_index"].to_numpy(dtype=float)

    out = np.full(len(targets), "normal_gap_mixed", dtype=object)

    # Order matters: a cell with no series history is cold no matter what else
    # is true, and a cell past the end of its series must extrapolate even if it
    # has ample cross-sectional support.
    country_thin = (n_country_period < THIN_SUPPORT) & (n_product_period >= THIN_SUPPORT)
    product_thin = (n_product_period < THIN_SUPPORT) & (n_country_period >= THIN_SUPPORT)
    out[country_thin] = "country_month_gap"
    out[product_thin] = "product_month_gap"

    forward = np.isfinite(last_seen) & (target_index >= last_seen)
    out[forward] = "future_or_latest_month_gap"
    out[n_series <= 0] = "new_country_product_unit_series"
    return pd.Series(out, index=targets.index, name="missingness_type")


def thinness_stratum(series_train_count) -> pd.Series:
    counts = pd.Series(series_train_count).fillna(0).astype(float)
    labels = pd.Series("12+", index=counts.index, dtype=object)
    labels[counts <= 0] = "0"
    labels[(counts >= 1) & (counts <= 2)] = "1-2"
    labels[(counts >= 3) & (counts <= 5)] = "3-5"
    labels[(counts >= 6) & (counts <= 11)] = "6-11"
    return labels


def prepare_targets(cells: pd.DataFrame, observed: pd.DataFrame, context=None):
    """Full target frame with context, derived keys and missingness type."""
    targets = build_targets(cells, observed)
    targets, unmatched = frames.attach_country_context(targets, context)
    targets = frames.add_derived_features(targets.assign(log_median_unit_value_usd=np.nan))
    targets["missingness_type"] = classify_missingness(targets, observed)
    return targets, unmatched
