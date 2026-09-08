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


def test_no_world_median_is_published_for_an_aggregate_node(built):
    """Straight off the build: only a leaf gets a `gmed`, so no client can
    reconstruct the ratio that has no referent."""
    for node, meta in built["nodeMeta"].items():
        leaf = built["tax"][node]["leaf"]
        assert ("gmed" in meta) is leaf, (node, sorted(meta))
    assert any(m.get("gmed") for m in built["nodeMeta"].values()), "nothing at all"


def _tiny_corpus(tax, leaves):
    months = ["2026-%02d" % m for m in range(1, 5)]
    rows = []
    for country in ("aa", "bb"):
        for p in months:
            for j, code in enumerate(leaves):
                for _ in range(3):
                    rows.append(
                        {
                            "country": country,
                            "currency": "USD",
                            "source": "shop",
                            "observation_date": pd.Timestamp(p + "-15"),
                            "coicop_code": code,
                            "pricing_basis": "retail",
                            "standard_unit": "kg",
                            "unit_value_local": 2.0 + j,
                            "unit_value_usd": 2.0 + j,
                            "mass_source": "declared",
                            "qa_status": "trusted",
                            "product_name": "x",
                            "fx_rate": 1.0,
                        }
                    )
    df = pd.DataFrame(rows)
    df["is_modelled"] = False
    df["is_derived"] = False
    df["period"] = df.observation_date.dt.to_period("M").astype(str)
    return df


def test_a_catch_all_leaf_gets_no_world_median_either(monkeypatch):
    """A residual leaf is a leaf, so only the residual rule can hold it out."""
    tax = {
        "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
        "01.1": {"t": "Rice", "p": "01", "lvl": 2, "leaf": True},
        "01.2": {"t": "Other cereals n.e.c.", "p": "01", "lvl": 2, "leaf": True},
    }
    monkeypatch.setattr(aggregate, "load_taxonomy", lambda: tax)
    monkeypatch.setattr(
        aggregate,
        "load_country_meta",
        lambda: {
            s: {"name": s, "iso3": s.upper(), "region": "R", "subregion": "S"}
            for s in ("aa", "bb")
        },
    )
    monkeypatch.setattr(
        aggregate, "load_observations", lambda: _tiny_corpus(tax, ["01.1", "01.2"])
    )
    built = aggregate.build_payload()

    assert built["residual"] == ["01.2"]
    assert "gmed" in built["nodeMeta"]["01.1"], "a named leaf keeps its yardstick"
    assert "gmed" not in built["nodeMeta"]["01.2"], "a catch-all leaf gets none"
    assert "gmed" not in built["nodeMeta"]["01"], "nor does an aggregate"


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
