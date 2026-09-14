"""The heatmap has one reading, and it is not dollars per unit.

A "US$ per unit" cell in that grid was a median of leaf unit values taken
across a whole COICOP class -- median dollars-per-kilo of "Cereals". The
members of a class are not the same good, so their unit values are not one
distribution and the median of them is not a price. Only the matched-leaf gap
survives aggregation, so only the matched-leaf gap is offered.
"""

from __future__ import annotations


def test_the_usd_per_unit_toggle_is_gone(page):
    assert page.locator("#hm-usd").count() == 0


def test_the_heatmap_renders_gaps_not_dollars(page):
    page.click("#t-world")
    page.wait_for_selector("#hmTbl td.c")
    # every populated cell is a signed percentage gap, never a dollar figure
    labels = page.locator("#hmTbl td.c").all_inner_texts()
    assert labels, "no heatmap cells rendered"
    assert all(v.startswith("+") or v.startswith("-") for v in labels), labels
    units = page.locator("#hmTbl td.ctry span.ru").all_inner_texts()
    assert units and all(v == "vs world" for v in units), units


def test_the_heatmap_caption_never_offers_a_dollar_reading(page):
    page.click("#t-world")
    page.wait_for_selector("#hmTbl td.c")
    assert "US$" not in page.inner_html("#hmSub")
    assert "cheapest in the row" not in page.inner_html("#hmRamp")


def test_no_client_state_can_bring_the_dollar_reading_back(page):
    """The branch is deleted, not hidden -- an old bookmarked state is inert."""
    page.click("#t-world")
    page.evaluate("APP.set('hmode','usd')")
    page.wait_for_selector("#hmTbl td.c")
    labels = page.locator("#hmTbl td.c").all_inner_texts()
    assert all(v.startswith("+") or v.startswith("-") for v in labels), labels
