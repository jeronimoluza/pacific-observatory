"""The official CPI can only be benchmarked against in its own currency.

An official CPI is a LOCAL-CURRENCY index; every series this dashboard builds
is in US dollars. Laying one over the other unconverted puts the exchange rate
inside the comparison, which is the misreading the Currency-effects tab exists
to prevent. So the overlay applies the FX identity to OUR line --

    d ln P_local = d ln P_usd + d ln FX

-- and leaves the published index alone. That has no meaning above one country,
so the overlay is country-mode only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from conftest import CPI_FOOD, CPI_HEADLINE, FX_DRIFT  # noqa: E402
from prices.explorer import cpi as explorer_cpi  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")


# ------------------------------------------------------------ the cache bug


def test_the_imf_cache_key_carries_the_component():
    """Without this, asking for food returned the cached headline, silently."""
    from cpi.imf_data import cpi as imf

    food = imf._cache_path("FJI", "M", "CP01")
    head = imf._cache_path("FJI", "M", "_T")
    assert food != head
    assert food.name == "FJI.cpi.CP01.M.csv"
    assert head.name == "FJI.cpi._T.M.csv"


def test_a_food_request_never_reads_a_headline_cache(tmp_path, monkeypatch):
    """The regression itself: a `_T` file on disk must not answer for CP01."""
    from cpi.imf_data import cpi as imf

    monkeypatch.setattr(imf, "IMF_ROOT", tmp_path)
    legacy = tmp_path / "FJI.cpi.M.csv"
    legacy.write_text("TIME_PERIOD,value\n2025-M01,100.0\n")

    fetched = {}

    def fake_fetch(country, frequency, start_period, component):
        fetched["component"] = component
        return pd.DataFrame({"TIME_PERIOD": ["2025-M01"], "value": [222.0]})

    monkeypatch.setattr(imf, "_get_country_cpi_data", fake_fetch)

    headline = imf._load_or_fetch("FJI", "M", 2012, "_T")
    assert "component" not in fetched, "the legacy cache IS the headline"
    assert headline.value.tolist() == [100.0]

    food = imf._load_or_fetch("FJI", "M", 2012, "CP01")
    assert fetched["component"] == "CP01"
    assert food.value.tolist() == [222.0]


def test_the_wildcard_component_gets_a_cache_name_of_its_own():
    from cpi.imf_data import cpi as imf

    assert imf._cache_path("FJI", "M", "").name == "FJI.cpi.all.M.csv"


# ------------------------------------------------------------- the artifact


def test_the_artifact_is_optional(monkeypatch, tmp_path):
    """A build with no CPI table still produces a dashboard, minus the line."""
    monkeypatch.setattr(explorer_cpi, "OFFICIAL_CSV", tmp_path / "nope.csv")
    assert explorer_cpi.load_official({"fiji": "FJI"}) == {}


def test_the_artifact_is_rekeyed_onto_explorer_slugs(monkeypatch, tmp_path):
    path = tmp_path / "official.csv"
    path.write_text(
        "iso3,period,series,index_value\n"
        "FJI,2025-01,_T,100.0\n"
        "FJI,2025-02,_T,101.0\n"
        "FJI,2025-01,CP01,90.0\n"
        "TON,2025-01,_T,50.0\n"
    )
    monkeypatch.setattr(explorer_cpi, "OFFICIAL_CSV", path)
    got = explorer_cpi.load_official({"fiji": "FJI", "nauru": ""})
    assert set(got) == {"fiji"}
    assert got["fiji"]["_T"] == {"p": ["2025-01", "2025-02"], "v": [100.0, 101.0]}
    assert got["fiji"]["CP01"] == {"p": ["2025-01"], "v": [90.0]}


def test_every_division_the_imf_publishes_is_carried():
    """The dashboard is scoped to divisions 01 and 02; the table is not."""
    assert explorer_cpi.SERIES_LABEL["_T"] == "All items"
    assert [c for c in explorer_cpi.SERIES_LABEL if c != "_T"] == [
        "CP%02d" % i for i in range(1, 13)
    ]
    assert explorer_cpi.DIVISION_OF["CP01"] == "01"
    assert explorer_cpi.DIVISION_OF["CP02"] == "02"


def test_the_payload_exposes_the_block(built):
    """Empty is the correct value when the artifact has not been built."""
    assert "cpi" in built
    assert "cpiMeta" in built
    assert isinstance(built["cpi"], dict)


# ---------------------------------------------------------------- the chart


def _labels(page):
    return page.evaluate(
        "Chart.getChart('cWorldTrend').data.datasets.map(d => d.label)"
    )


def _series(page, i):
    return page.evaluate("Chart.getChart('cWorldTrend').data.datasets[%d].data" % i)


def _country_mode(page):
    page.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c00']);"
    )


def test_the_overlay_is_refused_above_one_country(page):
    page.evaluate("APP.setGeoMode('region'); APP.setGMeasure('chg12')")
    assert page.evaluate("document.getElementById('wv-cpi').disabled") is True
    assert "one country at a time" in page.get_attribute("#wv-cpi", "title")


def test_the_overlay_is_refused_on_a_level_or_a_base_100_index(page):
    page.evaluate("APP.setGeoMode('country'); APP.setGMeasure('index')")
    assert page.evaluate("document.getElementById('wv-cpi').disabled") is True
    page.evaluate("APP.setGMeasure('chg12')")
    assert page.evaluate("document.getElementById('wv-cpi').disabled") is False


def test_our_line_is_converted_to_local_currency_and_the_official_one_is_not(page):
    _country_mode(page)
    usd = _series(page, 0)
    page.evaluate("APP.toggleCPI()")
    local = _series(page, 0)
    fx = FX_DRIFT**12
    pairs = [(a, b) for a, b in zip(usd, local) if a is not None and b is not None]
    assert pairs, "nothing comparable was drawn"
    for a, b in pairs:
        assert b == pytest.approx(((1 + a / 100) * fx - 1) * 100, abs=1e-6)


def test_the_official_food_and_headline_indices_are_drawn_as_published(page):
    _country_mode(page)
    page.evaluate("APP.toggleCPI()")
    labels = _labels(page)
    assert any(
        "official CPI, food and non-alcoholic beverages" in v for v in labels
    ), labels
    assert any("official CPI, all items" in v for v in labels), labels

    food = labels.index([v for v in labels if "food and non" in v][0])
    drawn = [v for v in _series(page, food) if v is not None]
    assert drawn
    expected = (CPI_FOOD**12 - 1) * 100
    assert all(v == pytest.approx(expected, abs=1e-6) for v in drawn)

    head = labels.index([v for v in labels if "all items" in v][0])
    drawn = [v for v in _series(page, head) if v is not None]
    assert all(
        v == pytest.approx((CPI_HEADLINE**12 - 1) * 100, abs=1e-6) for v in drawn
    )


def test_the_axis_says_which_currency_it_is_in(page):
    _country_mode(page)
    y = "Chart.getChart('cWorldTrend').options.scales.y.title.text"
    assert page.evaluate(y).endswith(", US$")
    page.evaluate("APP.toggleCPI()")
    assert page.evaluate(y).endswith(", local currency")


def test_the_world_line_is_dropped_rather_than_drawn_in_a_currency_it_lacks(page):
    page.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['W', 'C:c00']);"
    )
    assert "World" in _labels(page)
    page.evaluate("APP.toggleCPI()")
    assert "World" not in _labels(page)


def test_the_conversion_is_stated_on_the_chart(page):
    _country_mode(page)
    page.evaluate("APP.toggleCPI()")
    warn = page.inner_text("#wtWarn")
    assert "our lines are converted to local currency" in warn
    assert "expenditure-weighted" in warn


def test_a_country_with_no_official_cpi_says_so(page):
    page.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['C:c05']); APP.set('gcpi', true);"
    )
    assert "No official CPI" in page.inner_text("#wtWarn")


def test_the_world_chip_goes_dead_rather_than_clickable_and_ignored(page):
    page.evaluate(
        "APP.setGFreq('M'); APP.setGeoMode('country'); APP.setGMeasure('chg12');"
        "APP.set('gsel', ['W', 'C:c00']);"
    )
    dead = "[...document.querySelectorAll('#wtChips .chip')].filter(e => e.disabled).length"
    assert page.evaluate(dead) == 0
    page.evaluate("APP.toggleCPI()")
    assert page.evaluate(dead) >= 1
    assert "many currencies" in page.evaluate(
        "[...document.querySelectorAll('#wtChips .chip')].find(e => e.disabled).title"
    )
