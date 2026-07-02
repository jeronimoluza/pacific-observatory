"""Build the traceable price time series from the GREEN artifact.

Each GREEN row is one deduped product keyed by ``input_hash``. This module joins
those keys back to ``raw_prices.csv`` — the ~20M-row DATED per-observation source
that ``prepare.py`` dedups into products_input — to recover every dated scrape of
each GREEN product, reapplies the product's stable tier-a unit-value transform to
each dated price, and attaches date-accurate FX -> USD. It emits a long parquet
(one row per ``input_hash`` x ``date``) with full provenance (product_url /
source / region), plus a small latest-snapshot CSV for dashboards.

``input_hash`` is recomputed row-wise on raw_prices.csv with the same
``prepare._row_input_dict`` + ``versioning.input_hash`` used to build
products_input, so the GREEN keys align — PROVIDED products_input.parquet is
current (rebuild via ``prices process --stage prepare`` if its hashes are stale).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_regions
from prices.build.fx import attach_fx_and_usd
from prices.enrich.config import RAW_PRICES_CSV, REPO_ROOT
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import _row_input_dict
from prices.enrich.versioning import input_hash as _input_hash

OUTPUTS_DIR = REPO_ROOT / "outputs" / "prices"
TIMESERIES_PARQUET = OUTPUTS_DIR / "eap_prices.parquet"
SNAPSHOT_CSV = OUTPUTS_DIR / "eap_prices_latest.csv"

# GREEN columns that describe the product (stable per input_hash) and travel onto
# every dated observation of it.
_GREEN_CARRY = [
    "input_hash",
    "amount_value",
    "count",
    "multiplier",
    "pricing_basis",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
]
# raw_prices.csv columns read from disk (keep the read narrow — ~20M rows).
# raw carries product_name (not product_name_original) + a native region column.
_RAW_COLS = [
    "product_name",
    "product_url",
    "source",
    "country",
    "currency",
    "price",
    "date",
    "region",
]
# Per-(input_hash, date) provenance kept from the first matching observation
# (product_url is inside the hash, so it is constant per input_hash).
_FIRST_COLS = [
    "product_name_original",
    "product_url",
    "source",
    "country",
    "region",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
]
_OUT_COLS = [
    "input_hash",
    "date",
    "product_name_original",
    "country",
    "region",
    "source",
    "product_url",
    "currency",
    "price",
    "unit_value_local",
    "unit_value_usd",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
]


def _country_region_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for region, rdata in load_regions().items():
        for _sub, sub_data in (rdata or {}).get("subregions", {}).items():
            for c in (sub_data or {}).get("countries", []):
                m[c] = region
    return m


def build_timeseries(
    green: pd.DataFrame, raw: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (long_df, snapshot_df).

    green: GREEN artifact rows (needs input_hash + the tier-a denom columns +
      coicop/base_item/form/variety + product_name_original).
    raw: dated per-observation rows (raw_prices.csv grain), with at least
      product_name, product_url, currency, price, date, source, country
      (region optional — derived from country when absent).
    """
    carry = green[[c for c in _GREEN_CARRY if c in green.columns]].drop_duplicates(
        subset=["input_hash"], keep="first"
    )
    green_hashes = set(carry["input_hash"].dropna().astype(str))
    green_names = set(green["product_name_original"].dropna().astype(str))
    if not green_hashes:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)

    pc = raw.copy()
    if "product_name_original" not in pc.columns:
        pc["product_name_original"] = pc["product_name"]
    # Prefilter by name (cheap) before recomputing hashes on the survivors.
    pc = pc[pc["product_name_original"].astype(str).isin(green_names)].copy()
    if pc.empty:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)
    pc["input_hash"] = [_input_hash(_row_input_dict(r)) for _i, r in pc.iterrows()]
    pc = pc[pc["input_hash"].isin(green_hashes)]
    if pc.empty:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)

    pc = pc.merge(carry, on="input_hash", how="left")
    derived = pc["country"].map(_country_region_map())
    if "region" in pc.columns:
        pc["region"] = pc["region"].where(pc["region"].astype(str).ne(""), derived)
        pc["region"] = pc["region"].fillna(derived)
    else:
        pc["region"] = derived
    pc["unit_value_local"] = [
        compute_unit_value(
            r.price, r.pricing_basis, r.amount_value, r.count, r.multiplier
        )
        for r in pc.itertuples()
    ]

    # Collapse to one row per (input_hash, date): median price/unit_value, first
    # provenance. product_url/source/region are constant per input_hash.
    grp = pc.groupby(["input_hash", "date"], dropna=False)
    agg = grp.agg(
        currency=("currency", "first"),
        price=("price", "median"),
        unit_value_local=("unit_value_local", "median"),
        **{c: (c, "first") for c in _FIRST_COLS},
    ).reset_index()

    fx_in = agg.rename(columns={"unit_value_local": "price_local", "date": "obs"})[
        ["price_local", "currency", "obs"]
    ].rename(columns={"obs": "observation_date"})
    fx_out = attach_fx_and_usd(fx_in)
    agg["unit_value_usd"] = fx_out["price_usd"].to_numpy()

    long_df = agg[_OUT_COLS].sort_values(["input_hash", "date"]).reset_index(drop=True)
    snapshot = _latest_snapshot(long_df)
    return long_df, snapshot


def _latest_snapshot(long_df: pd.DataFrame) -> pd.DataFrame:
    if long_df.empty:
        return long_df.copy()
    idx = long_df.groupby("input_hash")["date"].idxmax()
    return long_df.loc[idx].sort_values("input_hash").reset_index(drop=True)


def run(green_path: Path | str, raw_path: Path = RAW_PRICES_CSV) -> dict:
    """IO wrapper: read the accumulated GREEN artifact + raw_prices.csv, build the
    time series, and write the long parquet + latest-snapshot CSV."""
    green = pd.read_csv(green_path)
    raw = pd.read_csv(raw_path, usecols=_RAW_COLS, low_memory=False)
    long_df, snapshot = build_timeseries(green, raw)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    long_df.to_parquet(TIMESERIES_PARQUET, index=False)
    snapshot.to_csv(SNAPSHOT_CSV, index=False)
    return {
        "green_products": int(green["input_hash"].nunique())
        if "input_hash" in green.columns
        else 0,
        "matched_products": int(long_df["input_hash"].nunique()),
        "observations": int(len(long_df)),
        "parquet": str(TIMESERIES_PARQUET),
        "snapshot": str(SNAPSHOT_CSV),
    }
