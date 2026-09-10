"""Inputs for the explorer payload: paths, tuning constants, and loaders.

Split from `aggregate` to keep each module inside the repo's 500-line cap.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np  # noqa: F401
import pandas as pd
import pyarrow.parquet as pq
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
# Both gates above count LEAVES per country and say nothing about WHICH leaves.
# A leaf priced by three countries still entered all three baskets, so the three
# baskets were each a different basket, which is exactly what the matched
# construction claims they are not. This is the leaf gate: a leaf enters only
# where this share of the countries being compared price it. It doubles as the
# missing-price policy, stated once rather than left implicit in whatever the
# scrape happened to catch that month.
#
# THESE TWO GATES MULTIPLY, and the product has never been measured against the
# real corpus. After the share cut, no country can carry more leaves than the
# number of (leaf, unit) pairs that cleared it, so `MIN_BASKET_LEAVES` is now a
# demand for 15 pairs each priced in 75% of EVERY country in the payload. If
# fewer than 15 clear it, no country gets `level_ok`, and `level_ok` is what
# gates the country ranking, the heatmap and the waterfall -- three charts go
# blank at once, with only their own empty states to explain it. The eligible
# count is logged by `_basket_levels` on every build: read it before trusting a
# blank grid. Lower this share, or lower MIN_BASKET_LEAVES with it, if the log
# says the intersection is thin.
MIN_BASKET_LEAF_SHARE = 0.75

# The COICOP level the expenditure weights -- and the reader's sliders -- act
# on. 1 is the division, 3 the class.
#
# William asked for divisions, and divisions are what a CPI weight table
# publishes. They are also, right now, useless as a control: this dashboard
# carries two divisions and one of them contributes almost nothing to the
# eligible basket, so a division slider is one knob pinned at 100%. Class is
# where the World Bank's ICP actually stops for food, it is the grain the
# heatmap rows and the waterfall bars already use, and it is where the damage
# is: equal-per-class hands a class holding ONE leaf the same say as a class
# holding twelve. Set this to 1 to get his literal reading back; nothing else
# needs to change, and nothing here assumes which divisions are on screen.
BASKET_WEIGHT_LEVEL = 3

# Weight coverage: the share of the default weight vector a country actually
# prices. Under an equal average, MIN_BASKET_LEAVES was a serviceable proxy for
# breadth -- fifteen leaves is fifteen leaves. Under weights it stops being one:
# fifteen leaves that all sit inside cereals is a price level that is entirely
# cereals wearing a basket's name, and renormalising the missing categories away
# makes it look complete. This gate is quiet on the current corpus and gets loud
# exactly when the corpus thins, which is the shape a guard should have.
MIN_BASKET_WEIGHT_COVERED = 0.60

# ------------------------------------------------------------------ FX
# The FX table converts OUR US$ series into local terms so it can be laid over
# an official CPI, which is published in local currency. It is built from the
# per-row `fx_rate` of the observations themselves, and a country-month that
# mixes currencies has no single rate: Cambodia's rows are ~60% KHR (~4,027 per
# USD) and ~40% USD (1.0 exactly), so a plain median flips between two
# incompatible scales month to month and the 12-month conversion factor swings
# by 4,100x. The rows are right; the aggregation was not. So the median is taken
# over the country's DECLARED currency only (`countries.yaml: currency:`).
#
# Only RATIOS of the rate are ever used (`r1/r0`), so a series that is
# internally consistent at the wrong SCALE still converts correctly. That is why
# a legacy or successor ISO code is aliased onto the declared one rather than
# dropped -- Sierra Leone's rows are all old-scale SLL against a declared SLE,
# and their ratios are the ratios of the new leone. Codes are aliased ONLY where
# the two names denote the same currency: a redenomination (SLL/SLE, ZWL/ZWG) or
# a successor issued at par (XCG/ANG). A currency CHANGEOVER is not an alias --
# Bulgaria's BGN and EUR rows are two different units at 1.9558 to one, and
# merging them would manufacture exactly the break this filter exists to remove.
CURRENCY_ALIASES = {
    "SLL": "SLE",  # Sierra Leone, redenominated 1000:1 in 2022
    "ZWL": "ZWG",  # Zimbabwe, redenominated 2498.7:1 in 2024
    "XCG": "ANG",  # Caribbean guilder, replaced the Antillean guilder at par
}

# How far a country's rate may travel across the WHOLE series before the build
# says so. Not a filter -- the series is still published, because Venezuela's
# 962,000x really is Venezuela's. It is a tripwire: this defect was invisible for
# months because nothing looked, and every class of cause lands here. 20x is
# loose enough for ARS/TRY/NGN over a decade and tight enough that a mixed-scale
# median, a stale alias or a bad upstream rate cannot pass it quietly.
FX_SPAN_WARN = 20.0

# The second guard: a rate that leaves its own level and comes BACK. The span
# check says a country is odd; this says the cause is upstream rather than
# economic. A move must be at least this large to count as an excursion,
# the two months on either side of it must agree with each other to within
# FX_EXCURSION_RETURN, and it must last no longer than FX_EXCURSION_MAX_RUN --
# past that it is a regime, not a glitch. On the real corpus it fires on exactly
# three countries and all three are true: Mongolia (3,597 -> 0.753181 -> 3,547,
# a cross-derived rate merged into the FX cache), Syria (11,057 -> 110.6 -> 13,006,
# old and new pounds served under one SYP code across the 100:1 redenomination)
# and Zimbabwe (30,805 -> 13.4 -> 35,141, ZWG rates served under ZWL). Venezuela's
# clean one-way 1,000,000:1 cut does NOT fire it, which is the point.
FX_EXCURSION_RATIO = 3.0
FX_EXCURSION_RETURN = 1.5
FX_EXCURSION_MAX_RUN = 6

# A region's median over one or two countries is one of those countries' own
# price wearing a region's name. Below this a regional or subregional yardstick
# is not published at all, and the client says so rather than quietly reaching
# for the world median instead.
MIN_BENCH_COUNTRIES = 3

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
# Horizons for the year-over-year family, expressed in MONTHS and mapped to
# each frequency's own period count. A base-period index answers "how far has
# this drifted since some month we happened to start at", which is only as
# stable as that month; these answer "what has it done since a year ago", which
# needs no base at all. The 1-month entry is the previous-period change; at
# quarterly grain the shortest horizon a period can carry is three months.
CHANGE_LAGS = {"M": {1: 1, 12: 12, 24: 24, 36: 36}, "Q": {3: 1, 12: 4, 24: 8, 36: 12}}
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


def ladder_agg(
    leaves: pd.DataFrame,
    keys: list[str],
    val: str,
    how: str = "mean",
    k0: str | None = None,
    extra: dict[str, tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """Average a leaf statistic up the COICOP tree ONE LEVEL AT A TIME.

    Every figure this dashboard reports for an aggregate node — a price change,
    a chain link, a gap from the world — is built by comparing like with like at
    the deepest level and then averaging upward. Rice against rice, then the
    mean of the cereals, then the mean of the bread-and-cereals classes, then
    the mean of the food groups. Never the other way around: an average taken
    across a class before the comparison is an average over goods that are not
    the same good, and comparing two of those compares two different baskets.

    The change from a flat mean over every leaf beneath a node is a change of
    WEIGHT, and it is the point. A flat mean lets a densely enumerated corner of
    the taxonomy speak for its parent: `01.1.1` carries seven cereal leaves, and
    under a flat mean rice is a seventeenth of bread-and-cereals purely because
    the taxonomy happens to split cereals finely. Under the ladder every child
    of a node counts once, so a subclass of one leaf and a subclass of twenty
    weigh the same at their parent. Neither is a statement about consumption —
    there are no expenditure weights in this corpus — but only one of the two is
    a statement about the taxonomy rather than about prices.

    `k` counts the leaves underneath that actually contributed, summed up the
    ladder, so the publication gates keep the meaning they have always had.
    Pass `k0` when a leaf already stands for more than one observation.

    `how` is the estimator applied at every level. It is orthogonal to the
    ordering this function exists for: the chain in `geo` takes a median for
    reasons of its own and keeps taking one, level by level.

    NO GATE IS APPLIED HERE. A node too thin to publish on its own still passes
    its value to its parent, because the observation is real either way and the
    gate is about what may carry a headline, not about what counts as evidence.
    Callers apply `_link_need` to the result.
    """
    extra = extra or {}
    cols = keys + ["coicop_code", val] + [c for c, _ in extra.values()]
    cur = leaves[cols + ([k0] if k0 else [])].rename(columns={"coicop_code": "node"})
    cur = cur.copy()
    cur["_d"] = cur.node.str.count(r"\.") + 1
    cur["k"] = cur.pop(k0) if k0 else 1
    spec = {val: (val, how), "k": ("k", "sum")}
    spec.update({out: (src, how) for out, (src, how) in extra.items()})

    out = [cur]
    for d in range(int(cur._d.max()), 1, -1):
        step = cur[cur._d == d]
        if step.empty:
            continue
        up = step.assign(node=step.node.str.rsplit(".", n=1).str[0])
        up = up.groupby(keys + ["node"], observed=True).agg(**spec).reset_index()
        up["_d"] = d - 1
        cur = pd.concat([cur, up], ignore_index=True)
        out.append(up)
    return pd.concat(out, ignore_index=True).drop(columns="_d")


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
            # The currency the country's prices are quoted in. Carried because
            # the FX table has to filter on it -- dropping it here is what let
            # a median run across two currencies at once.
            "currency": (meta.get("currency") or "").strip().upper(),
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
    # Low-cardinality strings held as Python objects cost ~1 GB each over ~19M
    # rows -- `qa_status` has eight distinct values and burned 1.11 GB.
    # Dictionary-decoding straight to Categorical is ~19 MB each. Only columns
    # that are never a groupby key are converted: a categorical key under a
    # groupby that omits `observed=True` silently expands to the full cross
    # product. `currency` qualifies because its one groupby already passes it.
    cats = ["source", "qa_status", "mass_source", "currency", "pricing_basis"]
    df = pq.read_table(OBS_PATH, columns=cols).to_pandas(categories=cats)
    # Match on the ~170 categories, not on 19M rows: `.str.lower()` over a
    # categorical materialises the object array this conversion just avoided.
    modelled = [c for c in df.source.cat.categories if c.lower() in MODELLED_SOURCES]
    df["is_modelled"] = df.source.isin(modelled)
    df["is_derived"] = df.mass_source.eq("derived_typical")
    df["period"] = df.observation_date.dt.to_period("M").astype(str)
    return df
