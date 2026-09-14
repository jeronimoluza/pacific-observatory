"""The one public read of RT-CAL's released fills.

Both dashboards join the same table, so it is loaded and narrowed in one place.
Everything here is deliberately tolerant of RT-CAL never having run: the
explorer and the dashboard must build on a checkout where `prices rtcal run`
has not been executed, so a missing parquet returns an EMPTY frame with the
right columns rather than raising. A caller that left-joins an empty frame
gets exactly what it had before, which is the behaviour we want.

Only cells whose `release_status` is `released` are ever returned. The scored
targets and the holdout review queue are diagnostic artifacts and must not
reach a chart -- releasing is precisely the judgement the gate exists to make.
"""

from __future__ import annotations

import pandas as pd

from . import config

# What a consumer gets. `period` is the "YYYY-MM" string the summary parquet
# uses, NOT a Timestamp -- publish.py converts at its own boundary.
COLUMNS = ["country", "coicop_code", "standard_unit", "period", "usd", "prob"]
CELL_KEY = ["country", "coicop_code", "standard_unit", "period"]

_EMPTY = pd.DataFrame(
    {
        "country": pd.Series(dtype="object"),
        "coicop_code": pd.Series(dtype="object"),
        "standard_unit": pd.Series(dtype="object"),
        "period": pd.Series(dtype="object"),
        "usd": pd.Series(dtype="float64"),
        "prob": pd.Series(dtype="float64"),
    }
)


def load_released_fills(path=None) -> pd.DataFrame:
    """Released fills as (country, coicop_code, standard_unit, period, usd, prob).

    Empty when RT-CAL has not run. `prob` is the ISOTONIC-calibrated probability
    that the fill lands within 25% of the truth, which is the number a reader can
    act on; the raw gate score decides release but does not mean anything on its
    own scale.
    """
    src = path or config.RELEASED_FILLS_PARQUET
    if not src.exists():
        return _EMPTY.copy()

    f = pd.read_parquet(
        src,
        columns=[
            "country",
            "coicop_code",
            "standard_unit",
            "period",
            "predicted_median_unit_value_usd",
            "prob_within_25pct_calibrated",
            "release_status",
        ],
    )
    f = f[f["release_status"].eq("released")]
    f = f.rename(
        columns={
            "predicted_median_unit_value_usd": "usd",
            "prob_within_25pct_calibrated": "prob",
        }
    )[COLUMNS]

    # A non-positive fill is not a price. The gate scores in log space so this
    # should be impossible, but a chart is the wrong place to discover it.
    f = f[f["usd"].gt(0) & f["usd"].notna()]

    # One fill per cell. A duplicate would double-count in any groupby it lands
    # in, and the production run has no legitimate reason to emit one.
    return f.drop_duplicates(
        subset=["country", "coicop_code", "standard_unit", "period"]
    ).reset_index(drop=True)


_EMPTY_PRUNED = pd.DataFrame({c: pd.Series(dtype="object") for c in CELL_KEY})


def load_pruned_cells(path=None) -> pd.DataFrame:
    """Cells RT-CAL rejected as obvious price errors, keyed for an anti-join.

    These are meant to come OFF a chart, not merely out of a fit. The historical
    view carries values that are wrong on their face -- a loaf of bread at
    US$108/kg, a sack read as a kilo -- and drawing them costs a reader more than
    an empty month does. A gap that a fill can honestly occupy is the better
    outcome; a gap with no fill is still better than noise.

    Empty when RT-CAL has not run, so callers behave exactly as they did before.
    """
    src = path or config.PRUNED_CELLS_PARQUET
    if not src.exists():
        return _EMPTY_PRUNED.copy()
    return (
        pd.read_parquet(src, columns=CELL_KEY).drop_duplicates().reset_index(drop=True)
    )


def drop_pruned(
    df: pd.DataFrame, pruned: pd.DataFrame, code_col="coicop_code"
) -> pd.DataFrame:
    """Anti-join `df` against the pruned cells on the four-part cell key."""
    if pruned.empty or df.empty:
        return df
    key = ["country", code_col, "standard_unit", "period"]
    bad = set(map(tuple, pruned[CELL_KEY].astype(str).values))
    mask = [tuple(r) not in bad for r in df[key].astype(str).values]
    return df[mask]
