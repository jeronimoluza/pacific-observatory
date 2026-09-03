"""Inputs for the explorer payload: paths, tuning constants, and loaders.

Split from `aggregate` to keep each module inside the repo's 500-line cap.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
OBS_PATH = BUILD_DIR / "global_prices_observations.parquet"
COICOP_XLSX = REPO_ROOT / "data" / "prices" / "enrich" / "coicop_categories.xlsx"
COUNTRIES_YAML = REPO_ROOT / "src" / "configs" / "countries.yaml"
REGIONS_YAML = REPO_ROOT / "src" / "configs" / "regions.yaml"

# Cost-of-living survey aggregators: nobody observed a shelf. Kept for coverage,
# barred from the baseline cross-country comparison.
MODELLED_SOURCES = {"livingcost", "expatistan", "mylifeelsewhere", "numbeo"}

# `item` is the quantity-parse-failure bucket, not a fourth clean unit.
COMPARABLE_UNITS = ("kg", "lt", "unit")

MIN_CELL_OBS = 3
# Distinct months a cell needs before it is published as a series -- NOT
# consecutive months, they may sit anywhere in the span. Was 3, which carried no
# recorded justification and sat one above the median cell's 2 months, so it cut
# two thirds of leaf-grain series. 2 is the floor worth having: at a single
# period the trend decomposition divides an observation by itself and renders a
# confident "0.0%" that reads exactly like a genuinely flat price.
MIN_SERIES_PERIODS = 2

# A matched-basket index off six leaves is noise, and one bad-FX country can
# otherwise top the ranking. Both gates are deliberately conservative.
MIN_BASKET_LEAVES = 15
MIN_BASKET_SOURCES = 2

# Chained-index linking: a leaf links to its own previous observation, but only
# if that observation is recent enough for the link to mean anything.
MAX_LINK_GAP_MONTHS = 3
MIN_LINK_LEAVES = 8
# 78 of the 102 non-leaf nodes in divisions 01/02 hold fewer than MIN_LINK_LEAVES
# leaves in the taxonomy at all, so the flat gate locked them out of the chain no
# matter how much data ever arrived -- a taxonomy-shape problem wearing the
# clothes of a data problem. Below the flat bar the requirement scales to what a
# node can structurally supply, and the floor keeps "basket" meaning at least two
# distinct leaves, so a one-leaf node stays out rather than standing in for its
# whole parent. Anchored to the descendant count, which is structural: anchoring
# to observed maxima would read the August 2026 collection spike as the norm.
MIN_LINK_LEAVES_FRAC = 0.5
MIN_LINK_LEAVES_FLOOR = 2
# A chained index accumulates every link's error. Over this corpus the endpoint
# moves ~50% between MIN_LINK_LEAVES=3 and 12, so the index is published only
# where links are thick, and the per-month link count travels with it.
MIN_CHAIN_PERIODS = 6
# geography-level series (world / region / subregion / country): a link needs
# this many matched (country, leaf) pairs, and a series this many months.
GEO_MIN_LINK_PAIRS = 8
GEO_MIN_PERIODS = 4
# the two-way fixed-effects level: sweeps of alternating projection, and the
# recurring items a period needs before its effect is worth reporting
FE_ITERATIONS = 40
FE_MIN_PAIRS = 16
# At an aggregate node an "item" is a (country, leaf) pair, so 16 recurring
# items is a handful of countries. At a terminal node the leaf is pinned and an
# item collapses to a COUNTRY, so the same 16 silently demands 16 countries
# reporting one product in one period, in two periods. 81% of leaves never
# reach that, and South Asia -- 6 countries with comparable-unit data -- can
# never reach it at any threshold above 6. These are the leaf-grain counterparts.
# 4 was chosen off the observed support: the median region-leaf-quarter carries
# 2 countries and the 75th percentile carries 4.
FE_MIN_PAIRS_LEAF = 4
GEO_MIN_LINK_PAIRS_LEAF = 4
# how far apart two observations of the same item may be and still link
FREQ_MAX_GAP = {"Q": 1, "M": 3}
# an item this far in logs from its own median is a unit/decimal defect,
# not a price move — ln(20), comfortably above any real swing
DEFECT_LOG_RATIO = 3.0

# Relative (MAD) gates are structurally blind to systematic errors — a stale
# currency code or a thousands-separator misparse shifts a whole country by
# ~1000x and still looks internally consistent. These absolute per-unit bounds
# catch that class of defect. Cells outside them are FLAGGED, never dropped.
# Re-exported: the band is defined with the QA gate that enforces it per row,
# so the row gate and the cell gate cannot drift apart.
from prices.build.qa import PLAUSIBLE_USD  # noqa: E402,F401

# Above this share of flagged leaf cells a country is presumed to have an
# upstream FX/parse defect and is held out of cross-country rankings.
COUNTRY_DEFECT_SHARE = 0.20

_ISO3_TO_ISO2 = {}


def _levels(code: str) -> list[str]:
    """Every ancestor node of a COICOP code, itself included."""
    parts = code.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def load_taxonomy() -> dict[str, dict]:
    df = pd.read_excel(COICOP_XLSX, sheet_name="COICOP_2018", dtype=str)
    df = df[df.code.str.match(r"^(01|02)")].copy()
    tax = {}
    codes = set(df.code)
    for code, title in zip(df.code, df.title):
        clean = str(title).replace(" (ND)", "").replace(" (S)", "").strip()
        parent = ".".join(code.split(".")[:-1]) or None
        # A leaf is a node with no children, NOT a node at depth 5. Division 02
        # terminates at depth 4 -- it has no depth-5 codes at all -- so a
        # hardcoded `lvl == 5` made every alcohol and tobacco row invisible to
        # every series, index and ranking while still counting in the totals.
        tax[code] = {
            "t": clean,
            "p": parent,
            "lvl": len(code.split(".")),
            "leaf": not any(o != code and o.startswith(code + ".") for o in codes),
        }
    return tax


def load_country_meta() -> dict[str, dict]:
    props = yaml.safe_load(COUNTRIES_YAML.read_text()) or {}
    topo = yaml.safe_load(REGIONS_YAML.read_text()) or {}
    where = {}
    for region, rmeta in topo.items():
        for sub, smeta in (rmeta.get("subregions") or {}).items():
            for slug in smeta.get("countries") or []:
                where[slug] = (rmeta.get("name", region), smeta.get("name", sub))
    out = {}
    for slug, meta in props.items():
        region, subregion = where.get(slug, ("Unassigned", "Unassigned"))
        iso3 = (meta.get("iso3") or "").upper()
        out[slug] = {
            "name": meta.get("name", slug),
            "iso3": iso3,
            "region": region,
            "subregion": subregion,
        }
    return out


def load_observations() -> pd.DataFrame:
    cols = [
        "country",
        "currency",
        "source",
        "observation_date",
        "coicop_code",
        "pricing_basis",
        "standard_unit",
        "unit_value_local",
        "unit_value_usd",
        "mass_source",
        "qa_status",
        "product_name",
        "fx_rate",
    ]
    df = pd.read_parquet(OBS_PATH, columns=cols)
    df["is_modelled"] = df.source.str.lower().isin(MODELLED_SOURCES)
    df["is_derived"] = df.mass_source.eq("derived_typical")
    df["period"] = df.observation_date.dt.to_period("M").astype(str)
    return df
