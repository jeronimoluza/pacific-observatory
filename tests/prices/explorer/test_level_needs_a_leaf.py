"""A price in levels is only a price at a leaf of the COICOP tree.

"US$4.10 per kilo of cereals" divides one country's mix of rice, bread and
pasta by another country's mix. Aggregating across COUNTRIES is fine -- the
matched-leaf constructions do exactly that and are untouched here. Aggregating
across ITEMS is what has no referent, and this is the gate for it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prices.explorer import aggregate  # noqa: E402


def test_no_world_median_is_published_for_an_aggregate_node(monkeypatch, payload):
    """The gate is server-side, so no client can reconstruct the ratio."""
    for node, meta in payload["nodeMeta"].items():
        leaf = payload["tax"][node]["leaf"] and node not in payload["residual"]
        assert ("gmed" in meta) is leaf, node


def test_the_payload_gmed_pass_keeps_only_leaves():
    """Exercise the build's own filter rather than the fixture's copy of it."""
    tax = {
        "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
        "01.1": {"t": "Rice", "p": "01", "lvl": 2, "leaf": True},
        "01.2": {"t": "Other cereals n.e.c.", "p": "01", "lvl": 2, "leaf": True},
    }
    world_cells = pd.DataFrame(
        {
            "country": ["a", "a", "a", "b", "b", "b"],
            "node": ["01", "01.1", "01.2"] * 2,
            "standard_unit": ["kg"] * 6,
            "usd": [3.0, 2.0, 4.0, 3.5, 2.5, 4.5],
            "flagged": [False] * 6,
            "modelled": [0.0] * 6,
        }
    )
    residual = aggregate._residual_nodes(tax)
    leafy = world_cells.node.map(lambda c: bool(tax.get(c, {}).get("leaf")))
    clean = world_cells[
        leafy
        & ~world_cells.flagged
        & (world_cells.modelled < 0.5)
        & ~world_cells.node.isin(residual)
    ]
    got = clean.groupby(["node", "standard_unit"]).usd.median().to_dict()
    assert got == {("01.1", "kg"): 2.25}


# ---------------------------------------------------------------- client side


def test_compare_refuses_to_rank_an_aggregate_node(page):
    page.click("#t-compare")
    page.evaluate("APP.pick('01.1.1')")
    page.wait_for_function("document.querySelector('#cmpSub').innerText.length > 0")
    sub = page.inner_text("#cmpSub")
    assert "is a grouping, not an item" in sub
    assert page.inner_html("#cmpTbl") == "", "no value or ratio columns at an aggregate"
    assert page.evaluate("document.getElementById('cmp-abs').disabled") is True
    assert page.evaluate("document.getElementById('cmp-rel').disabled") is True


def test_compare_still_ranks_a_leaf(page):
    page.click("#t-compare")
    page.evaluate("APP.pick('01.1.1.1.1')")
    page.wait_for_selector("#cmpTbl tbody tr")
    assert page.locator("#cmpTbl tbody tr").count() == 20
    assert "World median" in page.inner_text("#cmpSub")
    assert page.evaluate("document.getElementById('cmp-rel').disabled") is False


def test_the_world_level_toggle_is_dead_at_an_aggregate_node(page):
    page.evaluate("APP.setGMeasure('index'); APP.setGNode('01.1.1')")
    page.wait_for_function("document.getElementById('wv-level').disabled !== undefined")
    assert page.evaluate("document.getElementById('wv-level').disabled") is True
    assert "grouping" in page.get_attribute("#wv-level", "title")


def test_the_world_level_toggle_is_live_at_a_leaf(page):
    page.evaluate("APP.setGMeasure('index'); APP.setGNode('01.1.1.1.1')")
    assert page.evaluate("document.getElementById('wv-level').disabled") is False


def test_the_matched_leaf_constructions_are_untouched(page):
    """The waterfall, the ranking and the heatmap all aggregate across
    COUNTRIES at a fixed leaf, which is the legitimate direction."""
    page.click("#t-patterns")
    page.wait_for_selector("#hmTbl td.c")
    assert page.locator("#hmTbl td.c").count() > 0
    assert "against a world median of 100" in page.inner_text("#wfNote")
    page.click("#t-world")
    page.wait_for_selector("#rankList .rrow")
    assert page.locator("#rankList .rrow").count() == 20
