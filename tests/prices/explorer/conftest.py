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
import sys
from pathlib import Path

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
    "01.1.1.2.1": "Bread",
    "01.1.1.2.2": "Pasta",
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
        if n in LEAVES:
            node_meta[n]["gmed"] = {
                "kg": round(2.0 + 0.5 * sorted(LEAVES).index(n) + 0.95, 4)
            }
        else:
            node_meta[n]["gmed"] = {"kg": 4.0}

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

    def series_block(ps, seed):
        return {
            "p": ps,
            "lvl": [round(3.0 + seed * 0.1 + 0.02 * k, 4) for k in range(len(ps))],
            "idx": [round(100.0 * (1.004**k), 2) for k in range(len(ps))],
            "k": [40] * len(ps),
            "c": [5] * len(ps),
        }

    gseries = {}
    for freq, ps in (("M", periods), ("Q", quarters)):
        for gi, gk in enumerate(geos):
            for node in ("01", "01.1", "01.1.1", "01.1.1.1.1"):
                gseries["%s|%s|%d|0" % (freq, gk, node_pos[node])] = series_block(
                    ps, gi
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

    return {
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
        "fx": {slug: {"p": periods, "r": [1.0] * len(periods)} for slug in cty_idx},
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
