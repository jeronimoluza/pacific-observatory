"""Expenditure weights, and the ladder they sit on top of.

The ladder gives every child of a node one vote. That is right when nothing is
known about how much people buy and wrong once something is: six of Macao's
classes hold a single beverage leaf each, all six carry broken unit values, and
one vote apiece handed them about a third of the basket. These tests pin the
arithmetic that stops the taxonomy's shape from deciding the answer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prices.explorer import aggregate, weights as weights_mod  # noqa: E402

# Two classes under one division. `sparse` holds ONE leaf, `dense` holds four --
# the Macao shape, in miniature. Titles avoid "other" and "n.e.c." so nothing
# here is treated as a catch-all residual.
TAX = {
    "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
    "01.1": {"t": "Food at home", "p": "01", "lvl": 2, "leaf": False},
    "01.1.1": {"t": "Cereals", "p": "01.1", "lvl": 3, "leaf": False},
    "01.1.2": {"t": "Water", "p": "01.1", "lvl": 3, "leaf": False},
    "01.1.1.1": {"t": "Grains", "p": "01.1.1", "lvl": 4, "leaf": False},
    "01.1.2.1": {"t": "Bottled", "p": "01.1.2", "lvl": 4, "leaf": False},
}
for i in range(1, 5):
    TAX[f"01.1.1.1.{i}"] = {"t": f"Grain {i}", "p": "01.1.1.1", "lvl": 5, "leaf": True}
TAX["01.1.2.1.1"] = {"t": "Bottled water", "p": "01.1.2.1", "lvl": 5, "leaf": True}

COLS = ["country", "node", "standard_unit", "usd", "modelled", "flagged", "sources"]


def _cells(rows):
    return pd.DataFrame(rows, columns=COLS)


def _corpus(water_usd):
    """Four countries priced identically except for country `a`'s water.

    Every country prices every leaf, so the 75% eligibility share cannot cut
    anything and the test is about the weighting alone.
    """
    rows = []
    for cty in ("a", "b", "c", "d"):
        for i in range(1, 5):
            rows.append([cty, f"01.1.1.1.{i}", "kg", 10.0, 0.0, False, 3])
        rows.append([cty, "01.1.2.1.1", "lt",
                     water_usd if cty == "a" else 1.0, 0.0, False, 3])
    return _cells(rows)


def _level(out, cty):
    return float(out.loc[out.country.eq(cty), "level"].iloc[0])


def test_a_single_leaf_class_dominates_until_it_is_weighted():
    """The Macao mechanism, in one assertion each way.

    Country `a` pays 32x the world for its one bottle of water and world price
    for everything else. Under equal-per-class that one leaf is HALF the basket,
    because its class is one of two. Under a weight vector that calls water a
    twentieth of spending, it is a twentieth.
    """
    cells = _corpus(32.0)

    equal = _basket(cells, None)
    assert _level(equal, "a") == pytest.approx(np.sqrt(32.0) * 100, rel=1e-9)

    weighted = _basket(cells, {"01.1.1": 0.95, "01.1.2": 0.05})
    assert _level(weighted, "a") == pytest.approx(32.0 ** 0.05 * 100, rel=1e-9)

    # the whole point, stated as a comparison rather than left to the reader
    assert _level(weighted, "a") < _level(equal, "a") / 3


def _basket(cells, w):
    return aggregate._basket_levels(cells, TAX, w)


def test_the_unweighted_path_is_untouched():
    """No weights table must mean exactly the behaviour that shipped before it.

    The fallback folds all the way to the divisions and averages those, rather
    than stopping at the weighted level with equal weights. The two differ
    whenever a division's classes are unevenly branched, and a missing CSV is
    not the moment to change what a number means.
    """
    cells = _corpus(4.0)
    out = _basket(cells, None)
    assert set(out.columns) >= {"country", "level", "n_leaves", "covered", "ok"}
    assert (out.covered == 1.0).all()
    assert _level(out, "b") == pytest.approx(100.0, rel=1e-9)


def test_a_missing_category_is_an_absent_term_not_a_zero():
    """Country `a` prices no water at all.

    Its weight is redistributed across what it does price, so the level is the
    cereals figure exactly -- not a figure dragged toward zero by a category
    that is simply not there. `covered` is what remembers the difference.
    """
    rows = []
    for cty in ("a", "b", "c", "d"):
        for i in range(1, 5):
            rows.append([cty, f"01.1.1.1.{i}", "kg", 20.0 if cty == "a" else 10.0,
                         0.0, False, 3])
        if cty != "a":
            rows.append([cty, "01.1.2.1.1", "lt", 1.0, 0.0, False, 3])
    out = _basket(_cells(rows), {"01.1.1": 0.6, "01.1.2": 0.4})

    a = out.loc[out.country.eq("a")].iloc[0]
    assert float(a.covered) == pytest.approx(0.6)
    assert float(a.level) == pytest.approx(200.0, rel=1e-9)

    b = out.loc[out.country.eq("b")].iloc[0]
    assert float(b.covered) == pytest.approx(1.0)


def test_weight_coverage_gates_a_country_that_prices_one_corner():
    """Fifteen leaves all inside one class is not a basket.

    `MIN_BASKET_LEAVES` cannot see this: it counts leaves and says nothing about
    which. Renormalisation then makes the hole invisible, which is exactly why
    the gate is on `covered` and not on the renormalised weights.
    """
    from prices.explorer.sources import MIN_BASKET_WEIGHT_COVERED

    rows = []
    for cty in ("a", "b", "c", "d"):
        for i in range(1, 5):
            rows.append([cty, f"01.1.1.1.{i}", "kg", 10.0, 0.0, False, 3])
        if cty != "a":
            rows.append([cty, "01.1.2.1.1", "lt", 1.0, 0.0, False, 3])
    out = _basket(_cells(rows), {"01.1.1": 0.3, "01.1.2": 0.7})
    a = out.loc[out.country.eq("a")].iloc[0]
    assert float(a.covered) == pytest.approx(0.3)
    assert float(a.covered) < MIN_BASKET_WEIGHT_COVERED
    assert not bool(a.ok)


def test_no_weights_table_falls_back_to_equal_and_says_so(monkeypatch, tmp_path):
    """A build with no CSV still produces a dashboard, and admits what it did."""
    monkeypatch.setattr(weights_mod, "WEIGHTS_CSV", tmp_path / "absent.csv")
    w, meta = weights_mod.default_weights(TAX, 3)
    assert w == {}
    assert meta["source"] == "equal"
    assert meta["n_reporting"] == 0


def test_the_default_vector_sums_to_one_over_the_taxonomy_on_screen():
    """Whatever the source publishes, the vector the client gets is a share of
    what is actually on this dashboard -- not of a national CPI basket that
    mostly is not."""
    from prices.explorer.sources import load_taxonomy

    tax = load_taxonomy()
    w, meta = weights_mod.default_weights(tax, 3)
    if not w:
        pytest.skip("no expenditure_weights.csv on this box")
    assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(v > 0 for v in w.values())
    assert set(w) <= {c for c, m in tax.items() if m.get("lvl") == 3}
    assert meta["n_reporting"] > 50
