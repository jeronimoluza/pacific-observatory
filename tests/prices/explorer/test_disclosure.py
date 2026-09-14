"""Model-shaped behaviours are disclosed rather than removed.

This file used to assert that nothing here was interpolated. That promise has
been kept in the only way that mattered and replaced in the way that did not.

What mattered was never that imputation is wrong. It was that an imputed value
would be INDISTINGUISHABLE on screen from a measured price move. RT-CAL answers
that objection instead of overruling it: a fill is labelled, is off by default,
is drawn as a hollow diamond rather than a dot, and carries the calibrated
probability that it lands within 25% of the truth. So the tests below assert the
new contract -- imputed cells are visible AS imputed -- rather than asserting the
absence of imputation.

What did not change is the blast radius. Fills reach the time-series display and
nothing else: not the chained index, not the leaf counts, not the basket.
Drawing a modelled point and letting it move an index are different commitments,
and only the first has been made. That is why the chain still says, truthfully,
that it interpolates nothing, and why the test asserting so is untouched.
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
    assert "fixed effects" in qa["fitted_level"]


def test_imputation_is_declared_with_its_scope_not_denied(built):
    """The old flag was a bare False. Its replacement has to say what and where."""
    interp = built["qa"]["interpolated"]
    assert isinstance(interp, dict), "a bare boolean cannot carry a scope"
    assert interp["method"] == "rtcal_v1"
    assert interp["labelled"] is True
    # Off by default: the reader opts INTO modelled points, never out of them.
    assert interp["default_visible"] is False
    # And the promise that keeps the chain's claim honest.
    assert interp["scope"] == ["series"]
    for downstream in ("chain", "changes", "basket", "heatmap", "cells"):
        assert downstream in interp["excluded_from"]
    assert "25%" in interp["probability"]


def test_a_fill_never_enters_a_measure_it_was_excluded_from(built):
    """The scope claim above is only worth anything if the payload obeys it.

    A series entry carries `imp` when it holds fills. No chain or changes entry
    may carry one, because fills never reach those measures -- if they ever do,
    this fails before the claim in the QA panel becomes a lie.
    """
    for key in ("chain", "changes"):
        for entry in built.get(key, {}).values():
            assert "imp" not in entry, f"{key} entry carries imputed points"


def test_imputed_points_are_off_by_default(page):
    """Default state is measured-only, whatever the payload contains."""
    assert page.evaluate("document.getElementById('imp-0').className") == "on"
    assert page.evaluate("document.getElementById('imp-1').className") == ""


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
