"""A synthetic explorer payload, rendered and driven in a real browser.

The explorer's arithmetic lives half in Python and half in `_app.js`, and the
half in JavaScript is where a level gets taken over a group of unlike items. A
source-text assertion cannot tell a deleted branch from a renamed one, so these
fixtures render the actual dashboard and read the actual DOM back.

The payload is hand-built rather than aggregated: the point is to control
exactly what the client is handed, including cases the real corpus happens not
to contain this month.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

UNITS = ["kg", "lt", "unit"]

# 01.1.1.* is a named class; 01.1.9.* is the taxonomy's catch-all, so its leaves
# read as residual and every LEVEL view has to drop them.
LEAVES = {
    "01.1.1.1.1": "Rice",
    "01.1.1.1.2": "Wheat",
    "01.1.1.1.3": "Maize",
    "01.1.1.2.1": "Bread",
    "01.1.1.2.2": "Pasta",
    "01.1.1.2.3": "Biscuits",
    "01.1.1.2.9": "Other bakery products n.e.c.",
    "01.1.9.1.1": "Other cereals n.e.c.",
    "01.1.9.1.2": "Other food products n.e.c.",
    "01.1.9.1.3": "Other bakery products",
}
BRANCHES = {
    "01": "Food and non-alcoholic beverages",
    "01.1": "Food",
    "01.1.1": "Cereals",
    "01.1.1.1": "Grains",
    "01.1.1.2": "Baked goods",
    "01.1.9": "Other food",
    "01.1.9.1": "Other food products",
}
N_COUNTRIES = 20

# ---- basket weights -------------------------------------------------------
# Three categories and a vector over them, small enough that the weighted sum
# can be checked by hand. The per-category log ratios are the country's own
# level plus offsets the PUBLISHED weights sum to exactly zero over, so
# applying `w0` to the matrix returns `cty[slug].level` and no other vector
# does -- which is what makes a parity assertion at `w0` mean something.
#
# `level` is left unrounded here, unlike the real build, because a parity gate
# of 0.01 cannot be told apart from a rounding of 0.1.
BW_CODES = ["01.1.1", "01.1.2", "01.1.3"]
BW_W0 = {"01.1.1": 0.5, "01.1.2": 0.3, "01.1.3": 0.2}
BW_OFF = {"01.1.1": 0.12, "01.1.2": -0.10, "01.1.3": -0.15}
BW_K = {"01.1.1": 14, "01.1.2": 13, "01.1.3": 13}
BW_LAB = {"01.1.1": "Cereals", "01.1.2": "Dairy", "01.1.3": "Fruit"}
BW_MIN_COV = 0.6
# Two countries with a hole in the basket, both still over the coverage floor,
# so the fixture ranks all twenty by default. Moving weight onto what c19 does
# not price is what takes it under -- see the gate test.
BW_DROP = {"c18": "01.1.3", "c19": "01.1.2"}
# The other two selectable vectors. The IMF one is division-shaped in the real
# payload; here it just has to be a different vector with the same keys.
BW_EQUAL = {c: 1.0 / len(BW_CODES) for c in BW_CODES}
BW_IMF = {"01.1.1": 0.2, "01.1.2": 0.4, "01.1.3": 0.4}


def bw_expect(slug, w):
    """The level and coverage `bwLevel` must return for `slug` under `w`.

    The same arithmetic as `_basket_levels` and as `_app.js`, written a third
    time on purpose: a test that reuses either implementation cannot catch the
    two agreeing on the wrong thing.
    """
    import math

    codes = [c for c in BW_CODES if c != BW_DROP.get(slug)]
    tot = sum(w[c] for c in BW_CODES)
    sw = sum(w[c] for c in codes if w[c] > 0)
    if sw <= 0 or tot <= 0:
        return None
    target = math.log((90.0 + int(slug[1:])) / 100.0)
    acc = sum(w[c] * (target + BW_OFF[c]) for c in codes if w[c] > 0)
    return {"level": math.exp(acc / sw) * 100.0, "covered": sw / tot,
            "n": sum(BW_K[c] for c in codes)}
# monthly compounding factors behind the fixture's FX and official-CPI series
FX_DRIFT = 1.005
CPI_HEADLINE = 1.004
CPI_FOOD = 1.007


def _tax() -> dict:
    tax = {
        c: {
            "t": t,
            "p": ".".join(c.split(".")[:-1]) or None,
            "lvl": len(c.split(".")),
            "leaf": False,
        }
        for c, t in BRANCHES.items()
    }
    for c, t in LEAVES.items():
        tax[c] = {
            "t": t,
            "p": ".".join(c.split(".")[:-1]),
            "lvl": len(c.split(".")),
            "leaf": True,
        }
    return tax


def make_payload() -> dict:
    tax = _tax()
    node_idx = sorted(tax)
    node_pos = {n: i for i, n in enumerate(node_idx)}
    cty_idx = ["c%02d" % i for i in range(N_COUNTRIES)]
    cty_pos = {c: i for i, c in enumerate(cty_idx)}

    cty = {}
    for i, slug in enumerate(cty_idx):
        cty[slug] = {
            "name": "Country %02d" % i,
            "iso3": "C%02d" % i,
            "region": "Region A" if i < 10 else "Region B",
            "subregion": "Sub %d" % (i // 5),
            "obs": 1000,
            "src": 3,
            "retail_src": 3,
            "cur": ["USD"],
            "leaves": len(LEAVES),
            "level": 90.0 + i,
            "level_n": 40,
            "level_ok": True,
            "defect": 0.0,
            "last": "2026-08",
        }
        # The published figures, taken from the matrix below rather than
        # asserted beside it: the client checks itself against these, and a
        # fixture whose headline disagrees with its own terms would fail the
        # check for a reason that has nothing to do with the code.
        exp = bw_expect(slug, BW_W0)
        cty[slug]["level"] = exp["level"]
        cty[slug]["level_n"] = exp["n"]
        cty[slug]["level_cov"] = exp["covered"]
        cty[slug]["level_gate"] = True
        cty[slug]["level_ok"] = exp["covered"] >= BW_MIN_COV

    # every leaf is priced by every country, at a price that walks with the
    # country index so the ranking and the heatmap both have something to order
    cells = {
        k: []
        for k in (
            "c",
            "n",
            "u",
            "usd",
            "loc",
            "cur",
            "obs",
            "mad",
            "src",
            "mod",
            "der",
            "mix",
            "flag",
            "per",
        )
    }
    for i, slug in enumerate(cty_idx):
        for j, leaf in enumerate(sorted(LEAVES)):
            usd = round(2.0 + 0.1 * i + 0.5 * j, 4)
            cells["c"].append(cty_pos[slug])
            cells["n"].append(node_pos[leaf])
            cells["u"].append(0)
            cells["usd"].append(usd)
            cells["loc"].append(usd)
            cells["cur"].append(0)
            cells["obs"].append(25)
            cells["mad"].append(0.1)
            cells["src"].append(3)
            cells["mod"].append(0.0)
            cells["der"].append(0.0)
            cells["mix"].append(False)
            cells["flag"].append(False)
            cells["per"].append("2026-08")
    # an aggregate node also carries cells, which is what lets a client build a
    # $/unit figure for a whole class unless something stops it
    for i, slug in enumerate(cty_idx):
        for node in ("01", "01.1", "01.1.1"):
            cells["c"].append(cty_pos[slug])
            cells["n"].append(node_pos[node])
            cells["u"].append(0)
            cells["usd"].append(round(3.0 + 0.1 * i, 4))
            cells["loc"].append(round(3.0 + 0.1 * i, 4))
            cells["cur"].append(0)
            cells["obs"].append(150)
            cells["mad"].append(0.2)
            cells["src"].append(3)
            cells["mod"].append(0.0)
            cells["der"].append(0.0)
            cells["mix"].append(False)
            cells["flag"].append(False)
            cells["per"].append("2026-08")

    node_meta = {}
    for n in node_idx:
        node_meta[n] = {
            "units": {"kg": 100},
            "dom": "kg",
            "n": 100,
            "countries": N_COUNTRIES,
        }
        # a world median exists only where a unit value does: at a leaf
        if n in LEAVES:
            node_meta[n]["gmed"] = {
                "kg": round(2.0 + 0.5 * sorted(LEAVES).index(n) + 0.95, 4)
            }

    periods = (
        ["2024-%02d" % m for m in range(1, 13)]
        + ["2025-%02d" % m for m in range(1, 13)]
        + ["2026-%02d" % m for m in range(1, 9)]
    )
    quarters = sorted({p[:4] + "Q" + str((int(p[5:]) - 1) // 3 + 1) for p in periods})

    geos = {"W": {"t": "World", "kind": "world", "n": N_COUNTRIES, "r": None}}
    for r in ("Region A", "Region B"):
        geos["R:" + r] = {"t": r, "kind": "region", "n": 10, "r": None}
    for slug in cty_idx:
        geos["C:" + slug] = {
            "t": cty[slug]["name"],
            "kind": "country",
            "n": 1,
            "r": cty[slug]["region"],
        }

    # 36 months of history is more than this fixture carries, so the 3-year
    # horizon is deliberately absent: a measure with no data must degrade to a
    # spoken message, not to a blank chart.
    HORIZONS = {"M": (1, 12, 24), "Q": (3, 12, 24)}

    def chg_value(months, k, seed):
        # the shortest horizon alternates sign, the way a real month-over-month
        # does: a smoother that works in logs would return NaN on the negatives
        if months in (1, 3):
            return (2.0 if k % 2 else -1.0) + seed * 0.001
        return {12: 12.0, 24: 25.0}[months] + seed * 0.01

    def series_block(ps, seed, freq):
        n = len(ps)
        chg = {}
        for months in HORIZONS[freq]:
            lag = months if freq == "M" else months // 3
            chg[str(months)] = {
                "v": [
                    None if k < lag else chg_value(months, k, seed) for k in range(n)
                ],
                "k": [0 if k < lag else 30 for k in range(n)],
            }
        return {
            "p": ps,
            "lvl": [round(3.0 + seed * 0.1 + 0.02 * k, 4) for k in range(n)],
            "idx": [round(100.0 * (1.004**k), 2) for k in range(n)],
            "k": [40] * n,
            "c": [5] * n,
            "chg": chg,
        }

    gseries = {}
    for freq, ps in (("M", periods), ("Q", quarters)):
        for gi, gk in enumerate(geos):
            for node in ("01", "01.1", "01.1.1", "01.1.1.1.1", "01.1.9.1.1"):
                gseries["%s|%s|%d|0" % (freq, gk, node_pos[node])] = series_block(
                    ps, gi, freq
                )

    series, chain = {}, {}
    for i, slug in enumerate(cty_idx[:4]):
        for node in ("01", "01.1.1.1.1"):
            k = "%d|%d|0" % (cty_pos[slug], node_pos[node])
            series[k] = {
                "p": periods,
                "usd": [
                    round(2.0 + 0.1 * i + 0.01 * j, 4) for j in range(len(periods))
                ],
                "loc": [
                    round(2.0 + 0.1 * i + 0.01 * j, 4) for j in range(len(periods))
                ],
                "n": [10] * len(periods),
            }
            chain[k] = {
                "p": periods,
                "idx": [round(100.0 * (1.003**j), 2) for j in range(len(periods))],
                "k": [9] * len(periods),
            }

    from prices.coicop import residual_leaves

    residual = sorted(residual_leaves(LEAVES))
    # a catch-all leaf gets no world median, exactly as the build now emits it
    for code in residual:
        node_meta[code].pop("gmed", None)

    return {
        "residual": residual,
        "meta": {
            "generated": "2026-09-08 00:00 UTC",
            "through": "2026-08",
            "n_obs": 100000,
            "n_countries": N_COUNTRIES,
            "n_nodes": len(node_idx),
            "n_sources": 12,
            "min_cell_obs": 3,
            "geo_min_pairs": 16,
            "divisions": ["01"],
        },
        "tax": tax,
        "nodeIdx": node_idx,
        "nodeMeta": node_meta,
        "ctyIdx": cty_idx,
        "cty": cty,
        "unitIdx": UNITS,
        "curIdx": ["USD"],
        "cells": cells,
        "series": series,
        "chain": chain,
        "geos": geos,
        "gseries": gseries,
        # c00's currency slides 0.5% a month against the dollar; everyone
        # else's is pegged. A conversion that is a no-op cannot be told from a
        # conversion that never ran.
        "fx": {
            slug: {
                "p": periods,
                "r": [
                    round(FX_DRIFT**k, 8) if slug == "c00" else 1.0
                    for k in range(len(periods))
                ],
            }
            for slug in cty_idx
        },
        "cpi": {
            "c00": {
                "_T": {
                    "p": periods,
                    "v": [
                        round(100.0 * CPI_HEADLINE**k, 6) for k in range(len(periods))
                    ],
                },
                "CP01": {
                    "p": periods,
                    "v": [round(100.0 * CPI_FOOD**k, 6) for k in range(len(periods))],
                },
            }
        },
        "cpiMeta": {
            "labels": {
                "_T": "All items",
                "CP01": "Food and non-alcoholic beverages",
            },
            "division": {"CP01": "01"},
            "source": "IMF, Consumer Price Index (IMF.STA:CPI), monthly index",
        },
        "basket": {
            "lvl": 3,
            "within": "equal-within-parent below the weighted level",
            "w0": BW_W0,
            "wmeta": {"source": "icp", "label": "a fixture", "n_reporting": 3,
                      "level": 3},
            "cty": {
                slug: {
                    c: [
                        math.log((90.0 + i) / 100.0) + BW_OFF[c],
                        BW_K[c],
                    ]
                    for c in BW_CODES
                    if c != BW_DROP.get(slug)
                }
                for i, slug in enumerate(cty_idx)
            },
            "lab": dict(BW_LAB, **{"01": BRANCHES["01"], "01.1": BRANCHES["01.1"]}),
            "modes": {
                "equal": {"w": BW_EQUAL,
                          "meta": {"source": "equal", "name": "Equal",
                                   "label": "equal weight over all 3 categories",
                                   "note": "One vote per category.",
                                   "n_reporting": 0, "level": 3,
                                   "unpriced": 0.0, "n_priced": 3}},
                "icp": {"w": BW_W0,
                        "meta": {"source": "icp", "name": "World Bank (ICP)",
                                 "label": "a fixture", "note": "Class depth.",
                                 "n_reporting": 3, "level": 3,
                                 "unpriced": 0.0, "n_priced": 3}},
                "imf": {"w": BW_IMF,
                        "meta": {"source": "imf_wgt_pt",
                                 "name": "IMF (national CPI weights)",
                                 "label": "a fixture",
                                 "note": "Division depth only.",
                                 "n_reporting": 3, "level": 3,
                                 "unpriced": 0.0, "n_priced": 3}},
            },
            "mode0": "icp",
            "gates": {"leaf_share": 0.75, "min_leaves": 15, "min_sources": 2,
                      "defect_share": 0.5, "min_covered": BW_MIN_COV},
        },
        "samples": {},
        "qa": {
            "status": {"trusted": 100000},
            "mass_source": {},
            "item_basis_rows": 0,
            "modelled_rows": 0,
            "modelled_sources": [],
            "plausible_bounds": {},
            "min_basket_leaves": 15,
            "history": {
                "latest_period": "2026-08",
                "share_latest_period": 0.1,
                "share_last_12m": 0.6,
                "min_link_leaves": 8,
            },
            "link_gap_months": {"chain": 3, "M": 3, "Q": 1},
            "fitted_level": "two-way fixed effects on log price (item + period)",
            "interpolated": False,
        },
    }


@pytest.fixture(scope="session")
def payload() -> dict:
    return make_payload()


@pytest.fixture(scope="session")
def explorer_html(payload, tmp_path_factory) -> Path:
    from prices.explorer import render

    out = tmp_path_factory.mktemp("explorer") / "explorer.html"
    out.write_text(render.render(payload))
    return out


@pytest.fixture(scope="session")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binaries not installed
            pytest.skip(f"chromium unavailable: {exc}")
        yield b
        b.close()


@pytest.fixture
def page(browser, explorer_html):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(explorer_html.as_uri())
    pg.wait_for_function("window.APP !== undefined")
    yield pg
    assert not errors, "JS errors on the page: " + json.dumps(errors)
    pg.close()


# ===================================================================== build
# A synthetic corpus run through the real `build_payload`, so the assertions
# below exercise the build's own filters rather than a copy of them written
# into the hand-built payload above.

TAX_BUILD = {
    "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
    "01.1": {"t": "Cereals", "p": "01", "lvl": 2, "leaf": False},
    "01.1.1": {"t": "Rice", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.2": {"t": "Bread", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.3": {"t": "Pasta", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.4": {"t": "Noodles", "p": "01.1", "lvl": 3, "leaf": True},
}
BUILD_LEAVES = ["01.1.1", "01.1.2", "01.1.3", "01.1.4"]
# `currency` is load-bearing: the FX table is the median over the country's OWN
# currency and nothing else, so a country meta without one gets no FX at all.
BUILD_CMETA = {
    "aa": {"name": "Aa", "region": "R1", "subregion": "S1", "currency": "USD"},
    "bb": {"name": "Bb", "region": "R1", "subregion": "S1", "currency": "USD"},
    "cc": {"name": "Cc", "region": "R2", "subregion": "S2", "currency": "USD"},
    "dd": {"name": "Dd", "region": "R2", "subregion": "S2", "currency": "USD"},
}
OBS_PER_CELL = 3


def _observations() -> pd.DataFrame:
    """A corpus dense enough to clear every gate the build applies."""
    months = ["2024-%02d" % m for m in range(1, 13)]
    months += ["2025-%02d" % m for m in range(1, 13)]
    months += ["2026-%02d" % m for m in range(1, 7)]
    rows = []
    for ci, country in enumerate(BUILD_CMETA):
        for i, p in enumerate(months):
            for j, code in enumerate(BUILD_LEAVES):
                for _ in range(OBS_PER_CELL):
                    rows.append(
                        {
                            "country": country,
                            "currency": "USD",
                            "source": "shop%d" % (ci % 2),
                            "observation_date": pd.Timestamp(p + "-15"),
                            "coicop_code": code,
                            "pricing_basis": "retail",
                            "standard_unit": "kg",
                            "unit_value_local": (2.0 + j + ci) * (1.01**i),
                            "unit_value_usd": (2.0 + j + ci) * (1.01**i),
                            "mass_source": "declared",
                            "qa_status": "trusted",
                            "product_name": "thing",
                            "fx_rate": 1.0,
                        }
                    )
    df = pd.DataFrame(rows)
    df["is_modelled"] = False
    df["is_derived"] = False
    df["period"] = df.observation_date.dt.to_period("M").astype(str)
    return df


@pytest.fixture
def built(monkeypatch):
    from prices.explorer import aggregate

    monkeypatch.setattr(aggregate, "load_taxonomy", lambda: TAX_BUILD)
    monkeypatch.setattr(
        aggregate,
        "load_country_meta",
        lambda: {k: dict(v, iso3=k.upper()) for k, v in BUILD_CMETA.items()},
    )
    monkeypatch.setattr(aggregate, "load_observations", _observations)
    return aggregate.build_payload()
