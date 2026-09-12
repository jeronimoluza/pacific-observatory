"""The external price level: the join, the arithmetic, and the chart.

The ranking is measured against the world median of our OWN corpus, so it
cannot be checked from inside. This module pins the three things that stand
between a benchmark and a decorative second axis:

  * an absent table degrades to an empty block rather than a crashed build,
  * the join is on ISO3 and neither drops a country silently nor duplicates
    one, and
  * the figure the client recomputes under the published weights is the figure
    the build published -- because if those two ever disagree, the reader is
    shown a disagreement between the two methods that is really a disagreement
    between two implementations of one method.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from conftest import BW_CODES, BW_DROP, BW_OFF, BW_W0, make_payload  # noqa: E402
from prices.explorer import ppp as ppp_mod  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")

HEADER = "iso3,code,value,round,source\n"


def _csv(tmp_path, body: str) -> Path:
    p = tmp_path / "bench.csv"
    p.write_text(HEADER + body)
    return p


# ----------------------------------------------------------- the artifact


def test_the_artifact_is_optional(monkeypatch, tmp_path):
    """A build with no benchmark table still produces a dashboard."""
    monkeypatch.setattr(ppp_mod, "PPP_CSV", tmp_path / "nope.csv")
    assert ppp_mod.load_benchmark({"fiji": "FJI"}) == ({}, {})


def test_the_payload_exposes_the_block(built):
    """Present and dict-shaped whether or not any country matched."""
    assert "ppp" in built
    assert "pppMeta" in built
    assert isinstance(built["ppp"], dict)
    assert isinstance(built["pppMeta"], dict)
    # the fixture's ISO3s are invented, so nothing joins -- and an empty block
    # is the correct answer, not a missing key
    assert built["ppp"] == {}


# ------------------------------------------------------------- the join


def test_the_join_is_on_iso3_and_ignores_the_slug(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV",
        _csv(tmp_path, "FJI,01,110,2021,icp\nFJI,02,90,2021,icp\n"))
    got, _ = ppp_mod.load_benchmark({"fiji-islands": "FJI"})
    assert set(got) == {"fiji-islands"}
    assert got["fiji-islands"]["icp01"] == 110.0


def test_a_country_with_no_iso3_is_dropped_rather_than_matched(
        monkeypatch, tmp_path):
    """Two explorer countries carry an empty iso3. Neither may borrow the
    other's benchmark, and an empty string must not match an empty row."""
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV",
        _csv(tmp_path, "FJI,01,110,2021,icp\n,01,999,2021,icp\n"))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI", "nowhere": "", "other": ""})
    assert set(got) == {"fiji"}


def test_an_unmatched_country_is_absent_not_null(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV", _csv(tmp_path, "FJI,01,110,2021,icp\n"))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI", "tonga": "TON"})
    assert "tonga" not in got


def test_two_slugs_on_one_iso3_both_get_it_and_neither_is_lost(
        monkeypatch, tmp_path):
    """A one-to-many join must fan out, not drop and not duplicate a row."""
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV", _csv(tmp_path, "FJI,01,110,2021,icp\n"))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI", "fiji-alt": "FJI"})
    assert set(got) == {"fiji", "fiji-alt"}
    assert got["fiji"] == got["fiji-alt"]


def test_the_output_holds_exactly_one_entry_per_matched_country(
        monkeypatch, tmp_path):
    """The CSV is long -- fifteen rows per economy -- and a join that fanned
    out on it would return a country several times over."""
    body = "".join(f"FJI,{c},{100 + i},2021,icp\n"
                   for i, c in enumerate(sorted(ppp_mod.ICP_SERIES.values())))
    monkeypatch.setattr(ppp_mod, "PPP_CSV", _csv(tmp_path, body))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI"})
    assert list(got) == ["fiji"]


# --------------------------------------------------------- the arithmetic


def test_the_weighted_reading_is_a_weighted_geometric_mean(
        monkeypatch, tmp_path):
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV",
        _csv(tmp_path,
             "FJI,01.1.1,200,2021,icp\n"
             "FJI,01.2,50,2021,icp\n"))
    w = {"01.1.1.1": 0.5, "01.2.1": 0.5}
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI"}, w)
    # exp(0.5*ln2 + 0.5*ln0.5) * 100 == 100
    assert got["fiji"]["icp"] == pytest.approx(100.0, abs=1e-6)


def test_a_missing_category_redistributes_rather_than_scoring_zero(
        monkeypatch, tmp_path):
    """`_basket_levels` treats a category a country does not price as an
    ABSENT TERM, never a zero. The benchmark has to do the same or the two
    numbers stop being comparable on exactly the countries with holes."""
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV", _csv(tmp_path, "FJI,01.1.1,200,2021,icp\n"))
    got, _ = ppp_mod.load_benchmark(
        {"fiji": "FJI"}, {"01.1.1.1": 0.25, "01.2.1": 0.75})
    assert got["fiji"]["icp"] == pytest.approx(200.0, abs=1e-6)
    assert got["fiji"]["icpCov"] == pytest.approx(0.25, abs=1e-9)


def test_with_no_weights_it_falls_back_to_the_two_divisions(
        monkeypatch, tmp_path):
    """The ranking's own unweighted fallback averages up to the divisions and
    takes their mean; the benchmark's must match it."""
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV",
        _csv(tmp_path, "FJI,01,400,2021,icp\nFJI,02,100,2021,icp\n"))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI"})
    assert got["fiji"]["icp"] == pytest.approx(200.0, abs=1e-6)


# ------------------------------------------------------------ the vintage


def test_the_round_year_travels_with_the_country(monkeypatch, tmp_path):
    """A 2011 benchmark has to read as a 2011 benchmark on screen. A price
    level is a real exchange rate; fifteen years of it is not a rounding."""
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV",
        _csv(tmp_path,
             "FJI,01,110,2021,icp\nSOM,01,80,2011,icp\n"))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI", "somalia": "SOM"})
    assert got["fiji"]["icpYear"] == 2021
    assert got["somalia"]["icpYear"] == 2011


# ------------------------------------------------------------- the bases


def test_the_wdi_series_is_rescaled_off_the_united_states(
        monkeypatch, tmp_path):
    """WDI publishes United States = 100 and everything else here is World =
    100. Drawing them on one 45-degree line without the conversion would put
    every country on earth below it."""
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV",
        _csv(tmp_path,
             "USA,GDP,150,2021,icp\n"
             "FJI,GDP,40,2025,wdi\n"))
    got, meta = ppp_mod.load_benchmark({"fiji": "FJI", "usa": "USA"})
    assert meta["us_on_world"] == 150.0
    assert got["fiji"]["wdi"] == pytest.approx(60.0)
    assert got["fiji"]["wdiYear"] == 2025


def test_without_the_united_states_no_wdi_value_is_invented(
        monkeypatch, tmp_path):
    monkeypatch.setattr(
        ppp_mod, "PPP_CSV", _csv(tmp_path, "FJI,GDP,40,2025,wdi\n"))
    got, _ = ppp_mod.load_benchmark({"fiji": "FJI"})
    assert "wdi" not in got.get("fiji", {})


# -------------------------------------------------------- the crosswalk


def test_every_weighted_category_is_covered_by_an_icp_index():
    """ICP stops at the class for food and at the GROUP for beverages, alcohol
    and tobacco. A category with nothing above it in the source is a silent
    hole in the benchmark's coverage."""
    sourced = {c for c in ppp_mod.ICP_SERIES.values() if c != "GDP"}
    assert ppp_mod._icp_node_for("01.1.1", sourced) == "01.1.1"
    assert ppp_mod._icp_node_for("01.2.1", sourced) == "01.2"
    assert ppp_mod._icp_node_for("02.1.1", sourced) == "02.1"
    assert ppp_mod._icp_node_for("02.3.1", sourced) == "02.3"
    assert ppp_mod._icp_node_for("03.1", sourced) is None


# ============================================================== the chart

BENCH_YEAR = 2021


def _ppp_payload() -> dict:
    """The fixture payload, plus a benchmark on the same three categories the
    weight sliders act on -- so the client's re-aggregation is exercised
    against the same vector the ranking uses.

    LIKE FOR LIKE, and written out rather than borrowed: the published `icp`
    runs over the categories the country actually prices, which for `BW_DROP`'s
    two countries is two of the three, with the third's weight renormalised
    away exactly as `_basket_levels` does it on our own side. That is what
    `load_benchmark`'s `priced` argument buys, and pinning it here is what
    stops the client and the build drifting apart on the countries with a hole
    -- the only countries where the restriction is visible at all.
    """
    p = make_payload()
    cls_vals = {"01.1.1": 120.0, "01.1.2": 80.0, "01.1.3": 150.0}
    ppp = {}
    for i, slug in enumerate(p["ctyIdx"]):
        # a per-country tilt, so the scatter is not a single point
        vals = {c: v * (0.9 + 0.01 * i) for c, v in cls_vals.items()}
        priced = [c for c in BW_CODES if c != BW_DROP.get(slug)]
        den = sum(BW_W0[c] for c in priced)
        acc = sum(BW_W0[c] * math.log(vals[c] / 100.0) for c in priced) / den
        ppp[slug] = {
            "cls": {c: [round(vals[c], 2), BENCH_YEAR] for c in BW_CODES},
            "icp": round(math.exp(acc) * 100.0, 2),
            "icpYear": BENCH_YEAR,
            "icp01": round(vals["01.1.1"], 2),
            "wdi": round(60.0 + i, 2),
            "wdiYear": 2025,
        }
    p["ppp"] = ppp
    p["pppMeta"] = {
        "labels": {"icp": "a fixture"},
        "base": "World = 100",
        "us_on_world": 150.0,
        "nodeOf": {c: c for c in BW_CODES},
        "source": "a fixture",
        "weighted": True,
        "n_icp": len(ppp),
        "n_wdi": len(ppp),
        "classes": BW_CODES,
    }
    return p


@pytest.fixture(scope="module")
def ppp_html(tmp_path_factory) -> Path:
    from prices.explorer import render

    out = tmp_path_factory.mktemp("ppp") / "explorer.html"
    out.write_text(render.render(_ppp_payload()))
    return out


@pytest.fixture
def ppp_page(browser, ppp_html):
    pg = browser.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(ppp_html.as_uri())
    pg.wait_for_function("window.APP !== undefined")
    pg.evaluate("APP.go('compare')")
    yield pg
    assert not errors, "JS errors on the page: " + json.dumps(errors)
    pg.close()


def _points(page, label):
    """What is actually plotted, read off the live chart rather than off the
    payload -- the point of a browser fixture is that a renamed field or a
    dropped dataset is a failure, not a silently empty scatter."""
    return page.evaluate(
        "(l) => { var c = Chart.getChart('cPpp'); if (!c) return null;"
        " var d = c.data.datasets.filter(s => s.label === l)[0];"
        " return d ? d.data.map(p => ({x:p.x, y:p.y,"
        "   slug:p.row ? p.row.slug : null})) : null; }", label)


def test_the_card_is_drawn_on_country_comparison(ppp_page):
    assert ppp_page.evaluate("!document.getElementById('pppCard').hidden")
    assert ppp_page.evaluate("!!Chart.getChart('cPpp')")


def test_the_card_is_absent_when_the_payload_carries_no_benchmark(page):
    """`page` is the shared fixture, whose payload has no `ppp` block at all."""
    page.evaluate("APP.go('compare')")
    assert page.evaluate("document.getElementById('pppCard').hidden") is True


def test_every_country_with_both_figures_is_plotted_exactly_once(ppp_page):
    pts = _points(ppp_page, "ranked") + (_points(ppp_page, "held out of the ranking") or [])
    slugs = [p["slug"] for p in pts]
    assert len(slugs) == len(set(slugs)), "a country was plotted twice"
    assert set(slugs) == set(ppp_page.evaluate("DATA.ctyIdx"))


def test_the_client_reproduces_the_published_benchmark_at_the_published_weights(
        ppp_page):
    """The whole card rests on this. The client re-aggregates the benchmark so
    it can follow a slider; at the PUBLISHED vector that re-aggregation has to
    return the figure the build published, or the reader is shown a gap between
    two methods that is really a gap between two implementations of one."""
    pts = _points(ppp_page, "ranked")
    assert pts
    published = ppp_page.evaluate("DATA.ppp")
    for pt in pts:
        assert pt["x"] == pytest.approx(published[pt["slug"]]["icp"], abs=0.01)


def test_our_own_figure_is_the_one_on_screen_not_a_second_copy(ppp_page):
    pts = _points(ppp_page, "ranked")
    ours = ppp_page.evaluate("DATA.cty")
    for p in pts:
        assert p["y"] == pytest.approx(ours[p["slug"]]["level"], abs=1e-9)


def test_the_benchmark_is_re_weighted_with_ours_rather_than_left_fixed(
        ppp_page):
    """Moving a slider moves OUR number. Leaving theirs at the published
    vector would turn a change of method into a change of price."""
    before = _points(ppp_page, "ranked")
    ppp_page.evaluate("APP.setWeight('01.1.3', 800, true)")
    after = _points(ppp_page, "ranked")
    bx = {p["slug"]: p["x"] for p in before}
    moved = [p["slug"] for p in after if abs(p["x"] - bx[p["slug"]]) > 0.5]
    assert moved, "the benchmark did not follow the weight vector"


def test_switching_benchmark_switches_the_axis(ppp_page):
    ax = "Chart.getChart('cPpp').options.scales.x.title.text"
    assert "ICP" in ppp_page.evaluate(ax)
    ppp_page.evaluate("APP.setPppBench('wdi')")
    assert "whole economy" in ppp_page.evaluate(ax)
    assert _points(ppp_page, "ranked")[0]["x"] == pytest.approx(60.0, abs=1e-6)


def test_the_correlation_is_stated_on_the_chart(ppp_page):
    """A scatter without its correlation on it is a picture, not a finding."""
    txt = ppp_page.inner_text("#pppStat").replace("\u00a0", " ")
    assert "countries" in txt
    assert "r = " in txt
    assert "slope" in txt
    assert "spread" in txt


def test_the_widest_disagreements_are_named(ppp_page):
    body = ppp_page.inner_text("#pppOut")
    assert body.strip(), "no outlier table"
    rows = ppp_page.evaluate("document.querySelectorAll('#pppOut tbody tr').length")
    assert 0 < rows <= 10


def test_both_axes_are_logarithmic(ppp_page):
    """Both numbers are ratios to a world median: 50 is as far below 100 as
    200 is above it, and a linear axis says otherwise."""
    for a in ("x", "y"):
        assert ppp_page.evaluate(
            "Chart.getChart('cPpp').options.scales.%s.type" % a) == "logarithmic"


def test_nothing_here_moves_the_ranking(ppp_page):
    """A benchmark that edited the figure it benchmarks would be a
    correction. `level` must read the same before and after the card draws."""
    before = ppp_page.evaluate("JSON.stringify(DATA.cty)")
    ppp_page.evaluate("APP.setPppBench('wdi'); APP.togglePppUngated();")
    assert ppp_page.evaluate("JSON.stringify(DATA.cty)") == before
