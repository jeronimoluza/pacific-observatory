"""The weight sliders, driven in a real browser.

There is no `node` on the build box, so the "read the function out of `_app.js`
and evaluate it" harness runs inside chromium instead: `bwLevel` is lifted out
of the source and re-evaluated against the page's own `DATA`, which is as close
to a unit test of that function as a closure allows. Everything else here goes
through the DOM, because the point of the panel is what a reader can see and do.

PARITY IS THE GATE. `basket.cty` is one half of a statistic whose other half is
a weight vector, and the client re-takes a sum the server already took. With the
sliders at the published vector the two numbers must be the same number. If they
are not, nothing else in this file matters -- the dashboard is showing a figure
that is not the one it published.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from conftest import (  # noqa: E402
    BW_CODES, BW_EQUAL, BW_IMF, BW_MIN_COV, BW_W0, N_COUNTRIES, bw_expect,
)

APP_JS = SRC / "prices" / "explorer" / "_app.js"
MODE_W = {"equal": BW_EQUAL, "icp": BW_W0, "imf": BW_IMF}
SLUGS = ["c%02d" % i for i in range(N_COUNTRIES)]


def _bwlevel_source() -> str:
    """The body of `bwLevel`, straight out of the shipped source. Asserting on
    source text cannot tell a renamed function from a deleted one, so this is
    only ever used to RUN it -- the assertion is on what it returns."""
    src = APP_JS.read_text()
    m = re.search(r"\nfunction bwLevel\(slug, w\) \{.*?\n\}\n", src, re.S)
    assert m, "bwLevel is gone from _app.js"
    return m.group(0)


def _client_levels(page, w: dict) -> dict:
    """Run the shipped `bwLevel` against the page's own payload."""
    return page.evaluate(
        """([src, w]) => {
             const codes = Object.keys(DATA.basket.w0).sort();
             const f = new Function("BW_CODES", "BW_CTY", "slug", "w",
                                    src + "\\nreturn bwLevel(slug, w);");
             const out = {};
             for (const s of DATA.ctyIdx) {
               out[s] = f(codes, DATA.basket.cty, s, w);
             }
             return out;
           }""",
        [_bwlevel_source(), w],
    )


@pytest.mark.parametrize("mode", ["equal", "icp", "imf"])
def test_the_client_reproduces_the_server_under_every_fixed_vector(page, mode):
    got = _client_levels(page, MODE_W[mode])
    worst = 0.0
    for slug in SLUGS:
        want = bw_expect(slug, MODE_W[mode])
        assert got[slug] is not None, slug
        worst = max(worst, abs(got[slug]["level"] - want["level"]))
        assert got[slug]["covered"] == pytest.approx(want["covered"], abs=1e-12)
        assert got[slug]["n"] == want["n"]
    assert worst < 0.01, f"{mode}: worst deviation {worst}"


def test_at_the_published_vector_the_client_matches_the_published_level(page):
    """The one that would actually mislead somebody: the dashboard opens on
    `w0`, and what it draws there has to be the figure in the parquet."""
    got = _client_levels(page, BW_W0)
    worst = max(
        abs(got[s]["level"] - page.evaluate(f"DATA.cty[{s!r}].level"))
        for s in SLUGS
    )
    assert worst < 0.01, worst


# ------------------------------------------------------------------ the panel
def _open(page):
    page.click("#t-compare")
    page.wait_for_selector("#rankList .rrow")


def _titles(page):
    return page.eval_on_selector_all(
        "#rankList .rrow", "els => els.map(e => e.title)")


def test_the_panel_draws_one_slider_per_category_in_code_order(page):
    _open(page)
    page.click("#wToggle")
    labels = page.eval_on_selector_all(
        "#wGrid .wrow .lab", "els => els.map(e => e.title.split(' ')[0])")
    assert labels == sorted(BW_CODES)
    assert page.locator("#wGrid input[type=range]").count() == len(BW_CODES)
    # grouped under the division and the group they sit in
    assert page.locator("#wGrid .wgrp").count() >= 1


def test_the_shares_on_screen_sum_to_a_hundred(page):
    """Slider values are raw and the sum is never held at one, so the number
    beside each slider is its NORMALISED share -- which means the column adds
    up, before and after a drag."""
    _open(page)
    page.click("#wToggle")

    def shares():
        return [float(t.rstrip("%")) for t in page.eval_on_selector_all(
            "#wGrid .wrow .num b", "els => els.map(e => e.textContent)")]

    assert sum(shares()) == pytest.approx(100.0, abs=0.2)
    page.evaluate("APP.setWeight('01.1.1', 320, 1)")
    assert sum(shares()) == pytest.approx(100.0, abs=0.2)


def test_a_slider_shows_what_it_was_moved_from(page):
    _open(page)
    page.click("#wToggle")
    assert page.locator("#wGrid .was").count() == 0     # nothing moved yet
    page.evaluate("APP.setWeight('01.1.1', 320, 1)")
    was = page.eval_on_selector_all("#wGrid .was", "els => els.map(e => e.textContent)")
    assert len(was) == len(BW_CODES)
    # 01.1.1 is half the published vector
    assert "50.0%" in was[0]


def test_reset_restores_the_published_figures_exactly(page):
    _open(page)
    before = _titles(page)
    page.evaluate("APP.setWeight('01.1.1', 40, 1)")
    assert _titles(page) != before
    page.evaluate("APP.resetWeights()")
    assert _titles(page) == before
    assert page.evaluate("document.getElementById('wBadge').hidden") is True


def test_a_ranking_that_is_not_the_published_one_says_so(page):
    _open(page)
    assert page.evaluate("document.getElementById('wBadge').hidden") is True
    page.evaluate("APP.setWeight('01.1.1', 40, 1)")
    assert page.evaluate("document.getElementById('wBadge').hidden") is False
    assert "not the published ranking" in page.inner_text("#wBadge")
    # a fixed vector that is not the default is just as much not the published
    # ranking, and gets the same badge
    page.evaluate("APP.setWMode('equal')")
    assert page.evaluate("document.getElementById('wBadge').hidden") is False
    page.evaluate("APP.setWMode('icp')")
    assert page.evaluate("document.getElementById('wBadge').hidden") is True


def test_moving_a_slider_under_a_fixed_vector_becomes_custom(page):
    _open(page)
    page.evaluate("APP.setWMode('equal')")
    assert page.evaluate("document.getElementById('wm-equal').className") == "on"
    page.evaluate("APP.setWeight('01.1.1', 400, 1)")
    assert page.evaluate("document.getElementById('wm-custom').className") == "on"
    # ...seeded from where the reader was, so Reset goes back there and not to
    # the published vector
    assert "Equal" in page.inner_text("#wReset")
    page.evaluate("APP.resetWeights()")
    assert page.evaluate("document.getElementById('wm-equal').className") == "on"


def test_a_country_crosses_the_coverage_floor_and_the_count_says_so(page):
    """c19 prices two of the three categories. Moving weight onto the one it
    does NOT price takes it under the floor, and it leaves the ranking -- which
    is correct, and has to be visible rather than a name quietly going missing.
    """
    _open(page)
    assert page.locator("#rankList .rrow").count() == N_COUNTRIES
    assert page.evaluate("DATA.cty['c19'].level_ok") is True

    # 01.1.2 to 400/1000, 01.1.1 to zero: c19 covers 0.2 of 0.7 -- under 0.6.
    page.evaluate("APP.setWeight('01.1.2', 400, 1)")
    page.evaluate("APP.setWeight('01.1.1', 0, 1)")
    assert page.evaluate("DATA.cty['c19'].level_cov") < BW_MIN_COV
    assert page.evaluate("DATA.cty['c19'].level_ok") is False
    assert page.locator("#rankList .rrow").count() == N_COUNTRIES - 1
    assert "1 fewer than the published weights" in page.inner_text("#worldCount")

    # ...and it comes back
    page.evaluate("APP.resetWeights()")
    assert page.locator("#rankList .rrow").count() == N_COUNTRIES
    assert "fewer" not in page.inner_text("#worldCount")


def test_the_corpus_half_of_the_gate_cannot_be_re_opened_by_a_weight(page):
    """A country the build refused on matched items or sources stays refused. A
    weight vector can only ever move the coverage half."""
    _open(page)
    page.evaluate("DATA.cty['c05'].level_gate = false")
    page.evaluate("APP.setWeight('01.1.1', 480, 1)")
    assert page.evaluate("DATA.cty['c05'].level_ok") is False


def test_the_vector_survives_the_url_hash(page, explorer_html):
    _open(page)
    page.evaluate("APP.setWMode('equal')")
    page.evaluate("APP.setWeight('01.1.3', 380, 1)")
    levels = page.evaluate(
        "DATA.ctyIdx.map(function (s) { return DATA.cty[s].level; })")
    frag = page.evaluate("window.location.hash")
    assert frag.startswith("#w=equal|") and "01.1.3:380" in frag

    page.goto(explorer_html.as_uri() + frag)
    page.wait_for_function("window.APP !== undefined")
    _open(page)
    assert page.evaluate("document.getElementById('wm-custom').className") == "on"
    assert page.evaluate(
        "DATA.ctyIdx.map(function (s) { return DATA.cty[s].level; })") == levels


def test_a_payload_without_a_weight_vector_hides_the_panel(browser, payload, tmp_path):
    """The pre-weights payload is still a payload. A panel of sliders that
    cannot change anything reads as broken, so it does not appear at all."""
    from prices.explorer import render

    stripped = json.loads(json.dumps(payload))
    stripped.pop("basket")
    out = tmp_path / "noweights.html"
    out.write_text(render.render(stripped))

    pg = browser.new_page()
    errs: list[str] = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(out.as_uri())
    pg.wait_for_function("window.APP !== undefined")
    pg.click("#t-compare")
    pg.wait_for_selector("#rankList .rrow")
    assert pg.evaluate("document.getElementById('wBox').hidden") is True
    assert pg.locator("#rankList .rrow").count() == N_COUNTRIES
    assert not errs, errs
    pg.close()
