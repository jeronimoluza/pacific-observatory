"""A published index that changes level has stopped being the same index.

`pctOver()` differences raw IMF index levels twelve months apart. Across a
rebase that is not an inflation rate, it is the ratio of two different bases:
Libya rebased all thirteen of its series at 2025-01 (CP01 353.9 -> 102.0) and
ZMB CP01 carries a one-month decimal error (464.47 -> 4755.04 -> 486.52) that
reads as +1042% year on year. Seventy (iso3, series) pairs in the IMF table
exceed +/-100% on a twelve-month change and six exceed +1000%.

A single-month ratio outside [0.5, 2.0] is treated as a level break: the series
is CUT there rather than differenced across it, and the break is NAMED on
screen. A rebase is real information about the data and dropping it in silence
would be its own defect. A run of three or more such months is left alone --
that is a currency dying, and it is real.

The same file pins the display treatment for the changes that ARE real and ARE
enormous -- a symmetric-log axis rather than a clamp, because a clamp draws a
number that is not the number.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytestmark = pytest.mark.filterwarnings("ignore")

# The chart draws a 20-month window and the measure looks back 12, so only the
# last 8 columns can carry a point at all. Both defects are written into the
# window at positions that leave one drawable point on the far side of the
# break -- a cut that removed everything would prove nothing about the cut.
REBASE_BACK = 13  # periods[-13]: the month the base changes
SPIKE_BACK = 14  # periods[-14]: the month the decimal slips


@pytest.fixture(scope="module")
def broken_html(payload, tmp_path_factory) -> Path:
    """The same payload, with Libya's rebase and Zambia's spike written in."""
    from prices.explorer import render

    pl = copy.deepcopy(payload)
    head = pl["cpi"]["c00"]["_T"]
    at = len(head["p"]) - REBASE_BACK
    head["v"] = [round(v / 3.47, 6) if i >= at else v for i, v in enumerate(head["v"])]
    food = pl["cpi"]["c00"]["CP01"]
    at = len(food["p"]) - SPIKE_BACK
    food["v"] = [round(v * 10.24, 6) if i == at else v for i, v in enumerate(food["v"])]
    out = tmp_path_factory.mktemp("rebase") / "explorer.html"
    out.write_text(render.render(pl))
    return out


@pytest.fixture
def bpage(browser, broken_html):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(broken_html.as_uri())
    pg.wait_for_function("window.APP !== undefined")
    pg.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c00']); APP.toggleCPI();"
    )
    yield pg
    assert not errors, "JS errors on the page: " + json.dumps(errors)
    pg.close()


def _ds(page, needle):
    i = page.evaluate(
        "Chart.getChart('cWorldTrend').data.datasets"
        ".findIndex(d => d.label.indexOf(%s) >= 0)" % json.dumps(needle)
    )
    assert i >= 0, page.evaluate(
        "Chart.getChart('cWorldTrend').data.datasets.map(d => d.label)"
    )
    return page.evaluate("Chart.getChart('cWorldTrend').data.datasets[%d].data" % i)


def _grid(page):
    return page.evaluate("Chart.getChart('cWorldTrend').data.labels")


def _period(page, back):
    return page.evaluate("DATA.cpi.c00._T.p.slice(-%d)[0]" % back)


def test_a_rebase_is_not_differenced_across(bpage):
    """Every window whose twelve months contain the break carries no point.

    Without this the chart reported Libya's change of base -- an index going
    353.9 to 102.0 -- as -71% inflation, thirteen series at once.
    """
    grid, v = _grid(bpage), _ds(bpage, "all items")
    b = grid.index(_period(bpage, REBASE_BACK))
    spanning = [i for i in range(len(grid)) if b <= i < b + 12]
    assert spanning
    assert all(v[i] is None for i in spanning), [(grid[i], v[i]) for i in spanning]


def test_the_series_survives_on_the_far_side_of_the_break(bpage):
    """Cut, not dropped. A window that BEGINS at the break is on one base the
    whole way and is still a perfectly good twelve-month change."""
    grid, v = _grid(bpage), _ds(bpage, "all items")
    b = grid.index(_period(bpage, REBASE_BACK))
    beyond = [i for i in range(len(grid)) if i >= b + 12]
    assert beyond, "the window is too short to prove anything"
    assert any(v[i] is not None for i in beyond), [(grid[i], v[i]) for i in beyond]


def test_a_one_month_decimal_spike_is_cut_at_both_edges(bpage):
    """ZMB CP01 steps up 10x and straight back down: 464.47, 4755.04, 486.52.

    Two breaks a month apart, and the spike month itself must not be compared
    with anything in either direction.
    """
    grid, v = _grid(bpage), _ds(bpage, "food and non")
    a = grid.index(_period(bpage, SPIKE_BACK))
    for i in (a, a + 1):
        assert v[i] is None
    html = bpage.inner_html("#wtWarn")
    assert grid[a] in html and grid[a + 1] in html


def test_a_calm_series_is_untouched(page):
    """The unmodified payload has no break, so nothing may be cut."""
    page.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c00']); APP.toggleCPI();"
    )
    v = _ds(page, "all items")
    assert any(x is not None for x in v)
    assert "changes level" not in page.inner_html("#wtWarn")


def test_the_break_is_named_on_screen_rather_than_left_as_a_gap(bpage):
    """A rebase is real information about the data. Silently dropping the
    months around it would trade one invisible defect for another."""
    html = bpage.inner_html("#wtWarn")
    assert "changes level" in html
    assert _period(bpage, REBASE_BACK) in html
    assert "change of base or a break in the feed" in html


# ------------------------------------------------- the hyperinflation axis


@pytest.fixture(scope="module")
def hyper_html(payload, tmp_path_factory) -> Path:
    """c00's currency loses six zeros' worth of value over the grid.

    Venezuela's shape. The conversion is a ratio, so this is what a genuine
    hyperinflation and a redenomination both look like on the way to the axis.
    """
    from prices.explorer import render

    pl = copy.deepcopy(payload)
    n = len(pl["fx"]["c00"]["p"])
    pl["fx"]["c00"]["r"] = [round(2.0**k, 6) for k in range(n)]
    out = tmp_path_factory.mktemp("hyper") / "explorer.html"
    out.write_text(render.render(pl))
    return out


@pytest.fixture
def hpage(browser, hyper_html):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(hyper_html.as_uri())
    pg.wait_for_function("window.APP !== undefined")
    pg.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c00']); APP.toggleCPI();"
    )
    yield pg
    assert not errors, "JS errors on the page: " + json.dumps(errors)
    pg.close()


def test_the_axis_goes_log_and_says_so(hpage):
    y = "Chart.getChart('cWorldTrend').options.scales.y"
    assert hpage.evaluate(y + ".title.text").endswith("log scale")
    assert hpage.evaluate("typeof (%s.ticks.callback)" % y) == "function"
    assert "symmetric log scale" in hpage.inner_html("#wtWarn")


def test_the_reader_is_told_the_number_may_be_a_redenomination(hpage):
    assert "redenomination rather than inflation" in hpage.inner_html("#wtWarn")


def test_the_drawn_value_is_transformed_but_the_real_one_is_kept(hpage):
    """A clamp would have replaced the number. This only moves where it sits."""
    raw = hpage.evaluate(
        "Chart.getChart('cWorldTrend').data.datasets[0].rawData.filter(v => v != null)"
    )
    plotted = hpage.evaluate(
        "Chart.getChart('cWorldTrend').data.datasets[0].data.filter(v => v != null)"
    )
    assert raw and len(raw) == len(plotted)
    # 4096x over twelve months, on top of our own small US$ drift
    assert max(raw) > 400000
    import math

    for a, b in zip(raw, plotted):
        assert b == pytest.approx(math.copysign(math.log10(1 + abs(a)), a), abs=1e-9)


def test_a_normal_country_keeps_a_linear_axis(page):
    page.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c00']);"
    )
    y = "Chart.getChart('cWorldTrend').options.scales.y"
    assert not page.evaluate(y + ".title.text").endswith("log scale")
    assert page.evaluate(
        "Chart.getChart('cWorldTrend').data.datasets[0].rawData === undefined"
    )
