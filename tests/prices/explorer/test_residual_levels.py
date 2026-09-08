"""Catch-all leaves are withheld from every LEVEL view and kept in the changes.

`publish` has withheld the cross-country figure on these leaves since it was
written; the explorer showed it. Two renderers reading the same taxonomy and
disagreeing about what is comparable is the defect this closes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prices import publish  # noqa: E402
from prices.coicop import residual_leaves  # noqa: E402
from prices.explorer import aggregate  # noqa: E402

TAX = {
    "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
    "01.1": {"t": "Bread and cereals", "p": "01", "lvl": 2, "leaf": False},
    "01.1.1": {"t": "Rice", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.2": {"t": "Other bakery products", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.3": {"t": "Other food products n.e.c.", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.4": {
        "t": "Cantaloupes and other melons, fresh",
        "p": "01.1",
        "lvl": 3,
        "leaf": True,
    },
    # an AGGREGATE whose own title says "other" -- excluded from levels because
    # it is an aggregate, never listed as a residual leaf
    "01.9": {"t": "Other food", "p": "01", "lvl": 2, "leaf": False},
}


def _cells(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "country",
            "node",
            "standard_unit",
            "usd",
            "modelled",
            "flagged",
            "sources",
        ],
    )


def test_publish_and_the_explorer_share_one_rule():
    assert publish._residual_leaves is residual_leaves
    assert publish._RESIDUAL_TITLE_RE is not None


def test_residual_nodes_are_leaves_only():
    r = aggregate._residual_nodes(TAX)
    assert r == {"01.1.2", "01.1.3"}
    assert "01.9" not in r, "an aggregate is not a residual LEAF"
    assert "01.1.4" not in r, "a named leaf that merely says 'other' survives"


def test_basket_level_drops_catch_all_leaves():
    """One country, four leaves, two of them catch-all.

    Every named leaf sits at exactly the world median, so the level must be
    100. The catch-all leaves sit at 4x and 1/4 of it; leave them in and the
    level moves off 100 whenever they are not perfectly offsetting.
    """
    rows = []
    for cty, mult in (("a", 1.0), ("b", 1.0), ("c", 1.0)):
        rows += [
            (cty, "01.1.1", "kg", 2.0 * mult, 0.0, False, 3),
            (cty, "01.1.4", "kg", 8.0 * mult, 0.0, False, 3),
        ]
    # only country "a" prices the catch-alls, and wildly off the others
    rows += [
        ("a", "01.1.2", "kg", 100.0, 0.0, False, 3),
        ("a", "01.1.3", "kg", 200.0, 0.0, False, 3),
        ("b", "01.1.2", "kg", 1.0, 0.0, False, 3),
        ("b", "01.1.3", "kg", 1.0, 0.0, False, 3),
    ]
    out = aggregate._basket_levels(_cells(rows), TAX).set_index("country")
    assert out.loc["a", "level"] == pytest.approx(100.0)
    assert out.loc["b", "level"] == pytest.approx(100.0)
    assert out.loc["a", "n_leaves"] == 2
    assert out.loc["b", "n_leaves"] == 2


def test_leaving_the_catch_alls_in_would_move_the_level():
    """The mutation guard: the same fixture without the filter is not 100."""
    rows = [
        ("a", "01.1.1", "kg", 2.0, 0.0, False, 3),
        ("b", "01.1.1", "kg", 2.0, 0.0, False, 3),
        ("a", "01.1.2", "kg", 100.0, 0.0, False, 3),
        ("b", "01.1.2", "kg", 1.0, 0.0, False, 3),
    ]
    cells = _cells(rows)
    kept = aggregate._basket_levels(cells, TAX).set_index("country")
    assert kept.loc["a", "level"] == pytest.approx(100.0)

    # Rename the catch-all and it is admitted: world median for 01.1.2 becomes
    # median(100, 1) = 50.5, so a's log gaps are (ln 1, ln 100/50.5) and the
    # median of those two is 0.34160 -> a level of 140.72, not 100.
    unfiltered = TAX | {"01.1.2": dict(TAX["01.1.2"], t="Croissants")}
    loose = aggregate._basket_levels(cells, unfiltered).set_index("country")
    assert loose.loc["a", "level"] == pytest.approx(140.72, abs=0.01)


# ---------------------------------------------------------------- client side


def test_the_navigator_hides_catch_all_items_and_says_so(page):
    page.click("#t-compare")
    page.evaluate("APP.pick('01.1.1.2')")
    page.wait_for_selector("#cmpNav .it")
    offered = page.eval_on_selector_all(
        "#cmpNav .it .code", "els => els.map(e => e.innerText.split(' ')[0])"
    )
    assert "01.1.1.2.1" in offered, offered  # Bread
    assert "01.1.1.2.9" not in offered, offered  # Other bakery products n.e.c.
    assert "1 catch-all item" in page.inner_text("#cmpNav")


def test_the_country_table_carries_no_catch_all_rows(page):
    page.click("#t-country")
    page.wait_for_selector("#ctryTbl tbody tr")
    body = page.inner_text("#ctryTbl")
    assert "Rice" in body
    assert "n.e.c." not in body
    assert "Other bakery" not in body


def test_the_heatmap_has_no_catch_all_row(page):
    page.click("#t-patterns")
    page.wait_for_selector("#hmTbl td.c")
    labels = page.locator("#hmTbl td.ctry").all_inner_texts()
    assert any("Cereals" in v for v in labels), labels
    assert not any("Other" in v for v in labels), labels


def test_compare_refuses_to_rank_a_catch_all_leaf(page):
    page.click("#t-compare")
    page.evaluate("APP.pick('01.1.9.1.1')")
    page.wait_for_function("document.querySelector('#cmpSub').innerText.length > 0")
    assert "catch-all" in page.inner_text("#cmpSub")
    assert page.inner_html("#cmpTbl") == ""


def test_the_change_measures_keep_the_catch_all_categories(page):
    """The level list and the change list are deliberately different."""

    def codes():
        return page.eval_on_selector_all(
            "#wtNode option", "els => els.map(e => e.value)"
        )

    page.evaluate("APP.setGMeasure('index')")
    with_changes = codes()
    page.evaluate("APP.setGMeasure('level')")
    with_levels = codes()
    assert "01.1.9.1.1" in with_changes, with_changes
    assert "01.1.1" in with_changes, "an aggregate node is fine for a change"
    assert "01.1.9.1.1" not in with_levels, with_levels
    assert with_levels == ["01.1.1.1.1"], with_levels


def test_the_difference_between_the_two_lists_is_stated_on_the_chart(page):
    page.evaluate("APP.setGMeasure('level')")
    page.wait_for_selector("#wtWarn .warnbox")
    assert "do not cover the same categories" in page.inner_text("#wtWarn")
