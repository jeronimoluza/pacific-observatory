"""The analytical deliverable: one current price per product per country.

Collapses the trusted observation history into a single current figure per
(country, leaf, unit), in local currency and in dollars.

Two choices are worth stating because neither is forced by the data:

  * PERIOD COLLAPSE is a trailing-3-month median, anchored on the latest trusted
    observation date rather than on wall-clock today (so a stale build reports
    the window it actually covers instead of an empty one). Three months is
    robust to a single bad scrape while still reading as current.

  * GRAIN keeps ``standard_unit`` in the key rather than collapsing to
    (country, leaf). A leaf priced per-kg in one source and per-count in another
    yields two series that must not be averaged together; this mirrors the key
    convention already established in ``unit_value_summary``.

``includes_derived_typical`` marks any cell that drew on a typical-mass
conversion, so a consumer wanting measured-only prices can filter on one column
instead of re-deriving provenance.

``unit_price_local`` carries an explicit ``currency``, and is computed inside
that one currency rather than over the whole cell -- see ``_local_price``.

``evidence`` says what the cell rests on. ``retail`` is an observed shelf price.
``modelled`` is a cost-of-living city average, and appears only where a country
has no retail listing for that leaf at all -- nine countries, all Pacific island
states, exist in this file for no other reason. A cell holding even one retail
row is a retail cell: the modelled rows are dropped from it rather than averaged
in, so a shelf-price median is never moved by a city average. Filter on this
column to get a retail-only file.

``derived_vs_measured_ratio`` is the honest quality flag on those conversions:
within a cell, the median converted unit value over the median measured one. A
value near 1 means the conversion lands where directly-measured rows already
sit. It runs high in aggregate, because rows whose quantity failed to extract
skew toward loose and bulk goods that are heavier than the packaged rows the
typical mass was derived from -- so the mass is too small and the price per kilo
comes out too high. The ratio is reported rather than gated on: gating would
delete precisely the cells that have no measured rows to compare against, which
are the ones the conversion exists to make visible. It is NaN where no
comparison is possible.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
ANALYTICAL_PARQUET = BUILD_DIR / "eap_fnb_analytical.parquet"

GRAIN = ["country", "coicop_code", "standard_unit"]
TRAILING_MONTHS = 3

OUTPUT_COLS = [
    "country", "coicop_code", "standard_unit",
    "unit_price_local", "currency", "n_obs_local",
    "unit_price_usd", "n_obs", "evidence",
    "includes_derived_typical", "derived_vs_measured_ratio",
    "window_start", "window_end",
]
SHIPPABLE_STATUS = ("trusted", "modelled_estimate")


def _derived_vs_measured(window: pd.DataFrame) -> pd.DataFrame:
    """Per-cell median(derived unit value) / median(measured unit value)."""
    by_source = (
        window.groupby(GRAIN + ["mass_source"], dropna=False)["unit_value_local"]
        .median()
        .unstack("mass_source")
    )
    for col in ("derived_typical", "measured"):
        if col not in by_source.columns:
            by_source[col] = np.nan
    ratio = by_source["derived_typical"] / by_source["measured"].replace(0, np.nan)
    return ratio.rename("derived_vs_measured_ratio").reset_index()


def _local_price(window: pd.DataFrame) -> pd.DataFrame:
    """Local-currency median taken inside ONE currency, plus which one.

    A cell is not guaranteed to be single-currency: Cambodia prices in KHR and
    USD side by side, Samoa in WST and NZD, and the cost-of-living aggregators
    quote USD wherever they operate. A median over a mixed cell is a number with
    no unit. So the local figure is computed over the cell's most-common
    currency only, and that currency is reported beside it. ``unit_price_usd``
    is unaffected and still uses every row, because USD is comparable by
    construction.
    """
    if "currency" not in window.columns:
        out = window.groupby(GRAIN, dropna=False).agg(
            unit_price_local=("unit_value_local", "median"),
            n_obs_local=("unit_value_local", "size"),
        ).reset_index()
        out["currency"] = pd.NA
        return out

    counts = window.groupby(GRAIN + ["currency"], dropna=False).size().rename("n")
    dominant = (
        counts.reset_index().sort_values("n", ascending=False)
        .drop_duplicates(GRAIN)[GRAIN + ["currency"]]
    )
    keyed = window.merge(dominant, on=GRAIN + ["currency"], how="inner")
    out = keyed.groupby(GRAIN + ["currency"], dropna=False).agg(
        unit_price_local=("unit_value_local", "median"),
        n_obs_local=("unit_value_local", "size"),
    ).reset_index()
    return out


def build_analytical(df: pd.DataFrame) -> pd.DataFrame:
    """Trailing-3-month median unit price per (country, leaf, unit)."""
    if df.empty or "qa_status" not in df.columns:
        return pd.DataFrame(columns=OUTPUT_COLS)

    trusted = df[df["qa_status"].isin(SHIPPABLE_STATUS)].copy()
    if trusted.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)
    if "evidence" not in trusted.columns:
        trusted["evidence"] = "retail"

    trusted["observation_date"] = pd.to_datetime(
        trusted["observation_date"], errors="coerce"
    )
    trusted = trusted[trusted["observation_date"].notna()]
    if trusted.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    anchor = trusted["observation_date"].max().to_period("M")
    window_periods = pd.period_range(end=anchor, periods=TRAILING_MONTHS, freq="M")
    trusted["period"] = trusted["observation_date"].dt.to_period("M")
    window = trusted[trusted["period"].isin(window_periods)]
    if window.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Retail wins inside a cell: where a shelf price exists, the modelled city
    # averages are dropped rather than pooled into the median. Cells left with
    # only modelled rows survive and are labelled -- that, and only that, is why
    # the Pacific island states appear here.
    has_retail = window.groupby(GRAIN, dropna=False)["evidence"].transform(
        lambda s: (s == "retail").any()
    )
    window = window[(window["evidence"] == "retail") | (~has_retail)]

    grp = window.groupby(GRAIN, dropna=False)
    out = grp.agg(
        unit_price_usd=("unit_value_usd", "median"),
        n_obs=("unit_value_local", "size"),
        evidence=("evidence", "first"),
    ).reset_index()
    out = out.merge(_local_price(window), on=GRAIN, how="left")

    if "mass_source" in window.columns:
        derived = grp["mass_source"].apply(lambda s: (s == "derived_typical").any())
        out["includes_derived_typical"] = derived.values
        out = out.merge(_derived_vs_measured(window), on=GRAIN, how="left")
    else:
        out["includes_derived_typical"] = False
        out["derived_vs_measured_ratio"] = np.nan

    out["window_start"] = str(window_periods[0])
    out["window_end"] = str(window_periods[-1])

    logger.info(
        "analytical file: %d rows over %s..%s (%d source rows, %d cells use a "
        "derived typical mass, %d cells rest on modelled estimates)",
        len(out), out["window_start"].iloc[0], out["window_end"].iloc[0],
        len(window), int(out["includes_derived_typical"].sum()),
        int((out["evidence"] == "modelled").sum()),
    )
    return out[OUTPUT_COLS]


def write_analytical(df: pd.DataFrame) -> pd.DataFrame:
    """Build the analytical file from a finalized frame and persist it."""
    out = build_analytical(df)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(ANALYTICAL_PARQUET, index=False)
    logger.info("wrote %s (%d rows)", ANALYTICAL_PARQUET, len(out))
    return out
