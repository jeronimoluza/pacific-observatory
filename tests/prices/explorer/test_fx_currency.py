"""An exchange rate is a rate BETWEEN two named currencies, not a number.

The overlay converts our US$ series into local terms so it can be laid over an
official CPI, using a monthly rate taken from the observations' own `fx_rate`.
That rate used to be the median over every row in a country-month, whatever
currency the row was quoted in. Cambodia's rows are ~60% KHR (~4,027 per USD)
and ~40% USD (1.0 exactly), so whichever side was more numerous that month won
the median outright and the series stepped between two scales 4,000x apart: a
2025-05 -> 2026-05 comparison was multiplied by 4,017, and the dashboard showed
roughly a million percent.

The rows were right. The aggregation was not. These pin the aggregation.
"""

from __future__ import annotations

import copy
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prices.explorer import aggregate as agg  # noqa: E402
from prices.explorer.sources import CURRENCY_ALIASES, FX_SPAN_WARN  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")


def _obs(rows: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    """(country, period, currency, fx_rate) -> the columns `_fx_table` reads."""
    df = pd.DataFrame(rows, columns=["country", "period", "currency", "fx_rate"])
    df["currency"] = df.currency.astype("category")
    return df


def _meta(**declared: str) -> dict[str, dict]:
    return {c: {"currency": v} for c, v in declared.items()}


# ------------------------------------------------------------- the defect


def test_a_month_mixing_two_currencies_medians_the_declared_one_only():
    """Cambodia, in miniature: more USD rows than KHR, and KHR must still win.

    A row count is not a vote on what a country's currency is.
    """
    obs = _obs(
        [("cambodia", "2026-05", "KHR", 4017.0)] * 2
        + [("cambodia", "2026-05", "USD", 1.0)] * 98
    )
    fx = agg._fx_table(obs, _meta(cambodia="KHR"))
    assert fx["cambodia"] == {"p": ["2026-05"], "r": [4017.0]}


def test_the_series_no_longer_steps_between_two_scales():
    """The 12-month conversion factor is what reached the screen."""
    obs = _obs(
        [("cambodia", "2025-05", "KHR", 4020.0)] * 2
        + [("cambodia", "2025-05", "USD", 1.0)] * 9
        + [("cambodia", "2026-05", "KHR", 4017.0)] * 9
        + [("cambodia", "2026-05", "USD", 1.0)] * 2
    )
    fx = agg._fx_table(obs, _meta(cambodia="KHR"))
    r0, r1 = fx["cambodia"]["r"]
    assert r1 / r0 == pytest.approx(0.99925, abs=1e-5)


def test_a_month_with_no_row_in_the_declared_currency_is_a_gap_not_a_one():
    """Cambodia has no KHR row at all in 2025-01 and 2025-02.

    The old median answered 1.0 there -- a real-looking rate off USD rows. A
    missing month is missing; `_app.js` returns null on either end and draws
    the gap.
    """
    obs = _obs(
        [("cambodia", "2025-01", "USD", 1.0)] * 17
        + [("cambodia", "2025-02", "USD", 1.0)] * 12
        + [("cambodia", "2025-03", "KHR", 4030.0)]
    )
    fx = agg._fx_table(obs, _meta(cambodia="KHR"))
    assert fx["cambodia"]["p"] == ["2025-03"]


# ------------------------------------------------------------- the aliases


def test_a_legacy_code_is_aliased_onto_the_currency_it_renames():
    """Sierra Leone declares SLE and its rows are all old-scale SLL.

    Only ratios of the rate are ever used, so a series that is internally
    consistent at the wrong scale converts correctly. Dropping those rows would
    cost the country its overlay to fix nothing.
    """
    assert CURRENCY_ALIASES["SLL"] == "SLE"
    obs = _obs(
        [("sierra_leone", "2025-01", "SLL", 22000.0)]
        + [("sierra_leone", "2025-01", "USD", 1.0)] * 5
    )
    fx = agg._fx_table(obs, _meta(sierra_leone="SLE"))
    assert fx["sierra_leone"]["r"] == [22000.0]


def test_the_alias_map_never_merges_two_different_units():
    """Every alias must be a rename or a par successor, never a changeover.

    Bulgaria's BGN and EUR rows are 1.9558 to one. An alias between them would
    manufacture exactly the break this filter exists to remove, so the map is
    asserted to hold only the three same-currency pairs it was built for.
    """
    assert CURRENCY_ALIASES == {"SLL": "SLE", "ZWL": "ZWG", "XCG": "ANG"}
    obs = _obs(
        [("bulgaria", "2025-01", "BGN", 1.80)]
        + [("bulgaria", "2026-09", "EUR", 0.86)]
    )
    fx = agg._fx_table(obs, _meta(bulgaria="BGN"))
    assert fx["bulgaria"]["r"] == [1.80]


# ------------------------------------------------------------- no overlay


def test_zero_rows_in_the_declared_currency_emits_no_entry_at_all():
    """Comoros declares KMF and every row it has is stamped EUR.

    An empty entry is worse than none: the client would find the country in
    `DATA.fx` and draw a converted line off nothing.
    """
    obs = _obs([("comoros", "2026-01", "EUR", 0.86)] * 1070)
    fx = agg._fx_table(obs, _meta(comoros="KMF"))
    assert "comoros" not in fx


def test_a_country_with_no_declared_currency_gets_no_entry_either():
    obs = _obs([("nowhere", "2026-01", "XXX", 3.0)])
    assert agg._fx_table(obs, {"nowhere": {}}) == {}


def test_the_countries_that_lose_an_overlay_are_named_in_the_log(caplog):
    obs = _obs([("comoros", "2026-01", "EUR", 0.86)])
    with caplog.at_level(logging.WARNING, logger=agg.logger.name):
        agg._fx_table(obs, _meta(comoros="KMF"))
    assert "comoros (declared KMF)" in caplog.text


# ------------------------------------------------------------- the guards


def test_an_implausible_span_is_shouted_about_at_build_time(caplog):
    """The real deliverable: the bug was invisible for months because the build
    never looked at the table it had just written."""
    obs = _obs(
        [("cambodia", "2025-01", "KHR", 1.0)] + [("cambodia", "2026-01", "KHR", 4017.0)]
    )
    with caplog.at_level(logging.WARNING, logger=agg.logger.name):
        agg._fx_table(obs, _meta(cambodia="KHR"))
    assert "FX SPAN: cambodia" in caplog.text


def test_a_currency_that_merely_slides_is_left_alone(caplog):
    obs = _obs([("aa", "2025-%02d" % m, "AAA", 10.0 * 1.02**m) for m in range(1, 13)])
    with caplog.at_level(logging.WARNING, logger=agg.logger.name):
        agg._fx_table(obs, _meta(aa="AAA"))
    assert "FX SPAN" not in caplog.text
    assert "FX EXCURSION" not in caplog.text


def test_a_rate_that_leaves_its_level_and_returns_is_called_a_rate_defect(caplog):
    """Mongolia: 22 days of cross-derived MNT rates merged into the FX cache.

    Distance from a currency's own long-run level does not discriminate -- it
    fires on every real redenomination and hyperinflation in the corpus. The
    RETURN does: hyperinflation goes one way, a redenomination steps once and
    stays, and only a bad rate has two shoulders that agree with each other.
    """
    obs = _obs(
        [("mongolia", "2025-10", "MNT", 3597.5)]
        + [("mongolia", "2025-11", "MNT", 0.753181)]
        + [("mongolia", "2025-12", "MNT", 3547.4)]
    )
    with caplog.at_level(logging.WARNING, logger=agg.logger.name):
        agg._fx_table(obs, _meta(mongolia="MNT"))
    assert "FX EXCURSION: mongolia" in caplog.text
    assert "2025-11" in caplog.text


def test_a_one_way_redenomination_is_not_called_a_rate_defect(caplog):
    """Venezuela cut six zeros in 2021-10 and never went back. That is a real
    event in the series, and the excursion check must not claim otherwise --
    the span check is what reports it."""
    obs = _obs(
        [("venezuela_rb", "2021-%02d" % m, "VES", 4.0e6) for m in (8, 9)]
        + [("venezuela_rb", "2021-%02d" % m, "VES", 4.2) for m in (10, 11, 12)]
    )
    with caplog.at_level(logging.WARNING, logger=agg.logger.name):
        agg._fx_table(obs, _meta(venezuela_rb="VES"))
    assert "FX EXCURSION" not in caplog.text
    assert "FX SPAN: venezuela_rb" in caplog.text


def test_the_span_threshold_is_loose_enough_for_a_real_soft_currency():
    """20x is a tripwire, not an opinion about monetary policy."""
    assert FX_SPAN_WARN >= 20.0


# ------------------------------------------------------------- end to end


def test_the_built_payload_still_ships_an_fx_entry_per_country(built):
    assert set(built["fx"]) == set(built["cty"])
    for g in built["fx"].values():
        assert len(g["p"]) == len(g["r"]) and g["p"]


# ------------------------------------------------ the gap, on the screen


@pytest.fixture(scope="module")
def gapped_html(payload, tmp_path_factory) -> Path:
    """One month struck out of the FX table, the way Cambodia loses 2025-01.

    Filtering to the declared currency costs Cambodia 2 of its 81 months --
    it has no KHR row at all in 2025-01 or 2025-02, only USD ones the old
    median was reading as a rate of 1.0. Those months have to come out.
    """
    from prices.explorer import render

    pl = copy.deepcopy(payload)
    fx = pl["fx"]["c00"]
    struck = fx["p"][-18]  # inside the window, twelve months before a drawn point
    keep = [i for i, q in enumerate(fx["p"]) if q != struck]
    pl["fx"]["c00"] = {
        "p": [fx["p"][i] for i in keep],
        "r": [fx["r"][i] for i in keep],
        "struck": struck,
    }
    out = tmp_path_factory.mktemp("fxgap") / "explorer.html"
    out.write_text(render.render(pl))
    return out


@pytest.fixture
def gpage(browser, gapped_html):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(gapped_html.as_uri())
    pg.wait_for_function("window.APP !== undefined")
    pg.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c00']);"
    )
    yield pg
    assert not errors, "JS errors on the page: " + json.dumps(errors)
    pg.close()


def _drawn(page):
    grid = page.evaluate("Chart.getChart('cWorldTrend').data.labels")
    return grid, page.evaluate("Chart.getChart('cWorldTrend').data.datasets[0].data")


def test_a_missing_rate_is_an_honest_gap_not_a_flat_line(gpage):
    """A month with no rate must draw nothing, not carry the last one forward
    and not fall to zero. The US$ line is unaffected: only the conversion is."""
    grid, before = _drawn(gpage)
    struck = gpage.evaluate("DATA.fx.c00.struck")
    hit = grid.index(struck)
    gpage.evaluate("APP.toggleCPI()")
    grid, after = _drawn(gpage)
    # the point twelve months after the struck month loses its rate ratio
    lost = hit + 12
    assert lost < len(grid), "the struck month is outside the drawable window"
    assert before[lost] is not None, "nothing was drawn there to begin with"
    assert after[lost] is None
    # and its neighbours are untouched
    assert after[lost + 1] is not None or before[lost + 1] is None
    assert after[lost - 1] is not None or before[lost - 1] is None
