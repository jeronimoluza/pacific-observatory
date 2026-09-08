"""The World chart opens on year-on-year, and base-100 is no longer the story.

A base-period index is read against a month that is itself one thin draw of a
sparse corpus, which is exactly what made it hard to defend. The change
measures compare period t with period t-k and stop there.
"""

from __future__ import annotations

import pytest


def _y_title(page):
    return page.evaluate(
        "Object.values(Chart.instances || {})"
        ".concat(Chart.getChart('cWorldTrend') ? [Chart.getChart('cWorldTrend')] : [])"
        "[0].options.scales.y.title.text"
    )


def _points(page):
    return page.evaluate("Chart.getChart('cWorldTrend').data.datasets.map(d => d.data)")


def test_year_on_year_is_what_opens(page):
    assert page.evaluate("document.getElementById('wv-chg12').className") == "on"
    assert page.evaluate("document.getElementById('wv-index').className") == ""
    assert page.evaluate("document.getElementById('wv-level').className") == ""
    assert _y_title(page) == "% change vs a year earlier, US$"


def test_the_year_on_year_line_carries_the_payload_values(page):
    """12.0% for the World series, straight off `chg["12"]`, unrebased."""
    data = _points(page)
    assert data, "nothing drawn"
    drawn = [v for series in data for v in series if v is not None]
    assert drawn, "every point was null"
    assert all(11.9 <= v <= 12.2 for v in drawn), sorted(set(drawn))[:8]


def test_every_horizon_is_reachable_and_changes_the_axis(page):
    page.evaluate("APP.setGFreq('M')")
    for measure, title, lo, hi in [
        ("chg1", "% change vs the previous month, US$", -1.1, 2.1),
        ("chg12", "% change vs a year earlier, US$", 11.9, 12.2),
        ("chg24", "% change vs 2 years earlier, US$", 24.9, 25.2),
    ]:
        page.evaluate("APP.setGMeasure('%s')" % measure)
        assert _y_title(page) == title
        drawn = [v for s in _points(page) for v in s if v is not None]
        assert drawn and all(lo <= v <= hi for v in drawn), (measure, drawn[:5])


def test_a_horizon_with_no_data_says_so_instead_of_drawing_nothing(page):
    """The fixture has under three years of history."""
    page.evaluate("APP.setGMeasure('chg36')")
    warn = page.inner_text("#wtWarn")
    assert "3 years earlier" in warn
    assert _points(page) == []


def test_the_shortest_horizon_follows_the_period_grain(page):
    page.evaluate("APP.setGFreq('M'); APP.setGMeasure('chg1')")
    assert _y_title(page) == "% change vs the previous month, US$"
    assert "previous month" in page.inner_text("#wv-chg1")
    page.evaluate("APP.setGFreq('Q')")
    assert _y_title(page) == "% change vs the previous quarter, US$"
    assert "previous quarter" in page.inner_text("#wv-chg1")
    drawn = [v for s in _points(page) for v in s if v is not None]
    assert all(-1.1 <= v <= 2.1 for v in drawn), drawn[:5]


def test_base_100_is_still_available_but_no_longer_leads(page):
    page.evaluate("APP.setGMeasure('index')")
    assert _y_title(page).startswith("Index, ")
    drawn = [v for s in _points(page) for v in s if v is not None]
    assert pytest.approx(100.0, abs=1e-6) == min(drawn)
    assert "hangs off the base" in page.inner_text("#wtWarn")


def test_the_support_count_follows_the_horizon_not_the_chain(page):
    """`k` on the series is the chain's link count; a change has its own."""
    page.evaluate("APP.setGMeasure('chg12')")
    note = page.inner_text("#wtNote")
    assert "30 item cells" in note, note
    page.evaluate("APP.setGMeasure('index')")
    assert "40 item cells" in page.inner_text("#wtNote")


def test_smoothing_a_change_averages_the_rate_not_its_logarithm(page):
    """A month-over-month change goes negative, and a negative has no log.

    The price smoother is a trailing GEOMETRIC mean, correct for prices and
    fatal here: it would return NaN for every window that straddles a fall.
    """
    page.evaluate("APP.setGMeasure('chg1'); APP.setGSmooth(2)")
    drawn = [v for s in _points(page) for v in s if v is not None]
    assert drawn, "nothing survived smoothing"
    assert all(v == v for v in drawn), "NaN in a smoothed change series"
    # +2.0 and -1.0 alternate, so a two-period trailing mean sits near +0.5
    assert any(abs(v - 0.5) < 0.05 for v in drawn), sorted(set(drawn))[:8]


def test_the_world_yardstick_keeps_a_chip_even_past_the_country_cap(page):
    """It is drawn by default; without a chip there was no way to switch it off."""
    page.evaluate("APP.setGeoMode('country'); APP.setGMeasure('chg12')")
    chips = page.locator("#wtChips .chip").all_inner_texts()
    assert len(chips) == 19, len(chips)
    assert chips[0].startswith("World"), chips[:3]
