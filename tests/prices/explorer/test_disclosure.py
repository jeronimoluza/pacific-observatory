"""Two model-shaped behaviours are disclosed rather than removed.

Nothing here is interpolated, and nothing here should be: some of the gaps in
this corpus are collection artefacts, and an imputed value would be
indistinguishable on screen from a measured price move. What the dashboard
owes the reader instead is a plain statement of the two places where its
arithmetic already goes beyond "two observations of the same item".
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prices.explorer import sources  # noqa: E402


def test_the_gap_constants_are_published_not_buried(built):
    """A reading built off a constant must travel with that constant."""
    qa = built["qa"]
    assert qa["link_gap_months"]["chain"] == sources.MAX_LINK_GAP_MONTHS
    assert qa["link_gap_months"]["M"] == sources.FREQ_MAX_GAP["M"]
    assert qa["link_gap_months"]["Q"] == sources.FREQ_MAX_GAP["Q"]
    assert qa["interpolated"] is False
    assert "fixed effects" in qa["fitted_level"]


def test_the_chain_says_it_bridges_gaps(page):
    page.evaluate("APP.setGFreq('M'); APP.setGMeasure('index')")
    warn = page.inner_text("#wtWarn")
    assert "up to 3 months" in warn
    assert "booked onto the later one" in warn
    assert "Nothing is interpolated" in warn


def test_the_price_level_says_it_is_fitted(page):
    page.evaluate("APP.setGMeasure('level')")
    warn = page.inner_text("#wtWarn")
    assert "fitted, not observed" in warn
    assert "fixed effects" in warn
    assert "no single shop was observed" in warn
    assert "(fitted)" in page.inner_text("#wv-level")


def test_the_change_measures_say_they_are_neither(page):
    page.evaluate("APP.setGMeasure('chg12')")
    warn = page.inner_text("#wtWarn")
    assert "Nothing here is interpolated or modelled" in warn
    assert "exactly 12 months apart" in warn


def test_the_fitted_level_is_not_the_default(page):
    """The default is a matched, exact-lag change: no model and no base."""
    assert page.evaluate("document.getElementById('wv-level').className") == ""
    assert page.evaluate("document.getElementById('wv-chg12').className") == "on"


def test_the_honesty_panel_states_that_no_gap_is_filled(page):
    foot = page.inner_text("#aboutFoot")
    assert "No missing month is ever filled in" in foot
    assert "up to 3 months" in foot
    assert "fitted model output" in foot
