"""The one switch that takes every prices gate to its arithmetic floor.

Nothing in this file is about whether a particular threshold is right. It is
about the switch being real: that it reaches every constant, that a diagnostic
build cannot land on a production path, and that it cannot ship a page without
saying what it is.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prices.explorer import profile  # noqa: E402

# Every gate the profile is responsible for, with the floor it must reach.
# `sources` and `publish` are read in a SUBPROCESS, because both take these by
# value at import time and a reimport inside a live process would not prove the
# thing this test is about.
EXPLORER_FLOORS = {
    "MIN_CELL_OBS": 1,
    "MIN_SERIES_PERIODS": 1,
    "MIN_BASKET_LEAVES": 1,
    "MIN_BASKET_SOURCES": 0,
    "MIN_BASKET_LEAF_SHARE": 0.0,
    "MIN_BASKET_WEIGHT_COVERED": 0.0,
    "MIN_BENCH_COUNTRIES": 1,
    "MIN_LINK_LEAVES": 1,
    "MIN_LINK_LEAVES_FRAC": 0.0,
    "MIN_LINK_LEAVES_FLOOR": 1,
    "MIN_CHAIN_PERIODS": 1,
    "GEO_MIN_LINK_PAIRS": 1,
    "GEO_MIN_LINK_PAIRS_LEAF": 1,
    "GEO_MIN_PERIODS": 1,
    "FE_MIN_PAIRS": 1,
    "FE_MIN_PAIRS_LEAF": 1,
}
PUBLISH_FLOORS = {"MIN_OBS_PER_CELL": 1, "COVERAGE_MIN_NAMED_LEAVES": 0}


def _read(module: str, names, env_on: bool) -> dict:
    code = textwrap.dedent(
        f"""
        import json, importlib
        m = importlib.import_module({module!r})
        print(json.dumps({{n: sorted(v) if isinstance(v, (set, frozenset)) else v
                   for n, v in ((n, getattr(m, n)) for n in {list(names)!r})}}))
        """
    )
    env = {"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"}
    if env_on:
        env["PO_PRICES_UNFILTERED"] = "1"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env
    )
    assert out.returncode == 0, out.stderr
    import json

    return json.loads(out.stdout)


def test_every_explorer_gate_reaches_its_floor():
    got = _read("prices.explorer.sources", EXPLORER_FLOORS, env_on=True)
    assert got == EXPLORER_FLOORS


def test_every_publish_gate_reaches_its_floor():
    got = _read("prices.publish", PUBLISH_FLOORS, env_on=True)
    assert got == PUBLISH_FLOORS


def test_the_normal_build_is_not_at_the_floor():
    # If this ever passes trivially the switch has stopped meaning anything:
    # somebody has already lowered every gate to its floor in the source.
    got = _read("prices.explorer.sources", EXPLORER_FLOORS, env_on=False)
    assert got != EXPLORER_FLOORS


def test_the_defect_tripwire_cannot_fire_when_unfiltered():
    # It is tested with a strict `<`, so its floor has to sit ABOVE 1.0 rather
    # than at it, or a country with a 100%-flagged basket is still held out.
    got = _read("prices.explorer.sources", ["COUNTRY_DEFECT_SHARE"], env_on=True)
    assert got["COUNTRY_DEFECT_SHARE"] > 1.0


def test_the_cost_of_living_aggregators_are_readmitted():
    got = _read("prices.explorer.sources", ["MODELLED_SOURCES"], env_on=True)
    assert got["MODELLED_SOURCES"] == []


def test_comparable_units_are_not_a_gate_and_do_not_move():
    # `item` is the quantity-parse-failure bucket. Admitting it would pool a
    # per-piece catch-all into a per-kilo median: arithmetic over incommensurable
    # quantities, which is a different thing from a weaker measurement.
    got = _read("prices.explorer.sources", ["COMPARABLE_UNITS"], env_on=True)
    assert "item" not in got["COMPARABLE_UNITS"]


def test_a_diagnostic_build_cannot_land_on_a_production_path(monkeypatch):
    monkeypatch.setattr(profile, "UNFILTERED", True)
    p = Path("/tmp/outputs/global_prices_explorer.html")
    assert profile.unfiltered_path(p).name == "global_prices_explorer_unfiltered.html"
    # idempotent, so a second pass through the CLI cannot stack suffixes
    assert profile.unfiltered_path(profile.unfiltered_path(p)) == profile.unfiltered_path(p)


def test_a_normal_build_keeps_the_path_it_was_given(monkeypatch):
    monkeypatch.setattr(profile, "UNFILTERED", False)
    p = Path("/tmp/outputs/global_prices_explorer.html")
    assert profile.unfiltered_path(p) == p


def test_the_banner_goes_in_and_says_what_the_page_is(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "UNFILTERED", True)
    f = tmp_path / "d.html"
    f.write_text('<html><head></head><body class="mode-explore"><h1>x</h1></body></html>')
    profile.stamp_unfiltered(f)
    html = f.read_text()
    assert 'class="mode-explore">' + profile.banner_html() in html
    assert "UNFILTERED DIAGNOSTIC BUILD" in html
    assert "single observation" in html


def test_a_normal_build_is_left_byte_identical(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "UNFILTERED", False)
    f = tmp_path / "d.html"
    f.write_text("<html><body>x</body></html>")
    profile.stamp_unfiltered(f)
    assert f.read_text() == "<html><body>x</body></html>"


def test_an_unstampable_page_raises_rather_than_shipping_unmarked(tmp_path, monkeypatch):
    # The failure this whole function exists to prevent is an unfiltered page
    # that looks like the real one, so a missing anchor must be loud.
    monkeypatch.setattr(profile, "UNFILTERED", True)
    f = tmp_path / "d.html"
    f.write_text("<html>no body tag here</html>")
    with pytest.raises(RuntimeError, match="refusing"):
        profile.stamp_unfiltered(f)


def test_both_templates_still_carry_the_anchor_the_stamp_needs():
    for tpl in (
        SRC / "prices" / "_publish_template.html",
        SRC / "prices" / "explorer" / "_template.html",
    ):
        assert "<body" in tpl.read_text(), tpl
