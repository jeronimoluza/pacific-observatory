"""The per-category matrix the sliders re-sum, and the vectors they switch between.

The ranking's headline is one number per country. It is a WEIGHTED SUM, and a
weighted sum cannot be re-taken from its own result -- so the payload ships the
terms as well, and everything here is about those terms still meaning what the
headline says they mean.

Two things are pinned:

  * applying `w0` to the matrix returns the level the build published, in plain
    numpy, with no explorer code in the loop. If that ever stops holding, a
    slider sitting at its default shows a different number from the one in the
    parquet, and the reader has no way to tell which is the dashboard's answer.

  * the three selectable vectors are vectors over ONE category set. `covered` is
    a share of whichever vector is live, so different category sets would make
    the coverage gate mean something different in each mode and the ranked
    counts across modes would stop being comparable.
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

from prices.explorer import aggregate  # noqa: E402
from prices.explorer import weights as weights_mod  # noqa: E402
from prices.explorer.sources import BASKET_WEIGHT_LEVEL  # noqa: E402

# Two divisions, four classes, unevenly branched -- the shape that makes the
# ladder and a flat mean disagree, and the shape a division-depth vector has to
# be spread over.
TAX = {
    "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
    "01.1": {"t": "Food at home", "p": "01", "lvl": 2, "leaf": False},
    "01.1.1": {"t": "Cereals", "p": "01.1", "lvl": 3, "leaf": False},
    "01.1.2": {"t": "Dairy", "p": "01.1", "lvl": 3, "leaf": False},
    "01.1.3": {"t": "Fruit", "p": "01.1", "lvl": 3, "leaf": False},
    "02": {"t": "Alcohol", "p": None, "lvl": 1, "leaf": False},
    "02.1": {"t": "Alcoholic beverages", "p": "02", "lvl": 2, "leaf": False},
    "02.1.1": {"t": "Beer", "p": "02.1", "lvl": 3, "leaf": False},
}
# Enough leaves that MIN_BASKET_LEAVES still clears when a whole class is
# dropped -- otherwise the coverage gate and the leaf gate fail together and
# the test cannot tell them apart, which is the one thing it exists to do.
_KIDS = {"01.1.1": 10, "01.1.2": 8, "01.1.3": 6, "02.1.1": 7}
for _cls, _n in _KIDS.items():
    TAX[_cls + ".1"] = {"t": "sub", "p": _cls, "lvl": 4, "leaf": False}
    for _i in range(1, _n + 1):
        TAX[f"{_cls}.1.{_i}"] = {
            "t": f"Item {_cls}.{_i}", "p": _cls + ".1", "lvl": 5, "leaf": True,
        }

CLASSES = ["01.1.1", "01.1.2", "01.1.3", "02.1.1"]
W0 = {"01.1.1": 0.45, "01.1.2": 0.25, "01.1.3": 0.20, "02.1.1": 0.10}
COLS = ["country", "node", "standard_unit", "usd", "modelled", "flagged", "sources"]
COUNTRIES = ("aa", "bb", "cc", "dd", "ee")


def _cells(drop: dict[str, str] | None = None) -> pd.DataFrame:
    """Every country prices every leaf, at a price that walks with its index, so
    no two countries land on the same level. `drop` removes one whole class from
    one country, which is the absent-term case."""
    drop = drop or {}
    rows = []
    for ci, cty in enumerate(COUNTRIES):
        for cls, n in _KIDS.items():
            if drop.get(cty) == cls:
                continue
            for i in range(1, n + 1):
                rows.append([cty, f"{cls}.1.{i}", "kg",
                             1.0 + 0.3 * ci + 0.11 * i, 0.0, False, 3])
    return pd.DataFrame(rows, columns=COLS)


def _reweight(matrix: dict, w: dict[str, float]) -> dict[str, dict]:
    """The weighted sum, in plain numpy. Deliberately NOT a call into
    `_basket_levels`: a test that reuses the implementation cannot tell the
    implementation from the definition."""
    tot = float(np.sum([w.get(c, 0.0) for c in w]))
    out = {}
    for cty, terms in matrix.items():
        codes = [c for c in terms if w.get(c, 0.0) > 0]
        if not codes:
            continue
        wv = np.array([w[c] for c in codes])
        rv = np.array([terms[c][0] for c in codes])
        out[cty] = {
            "level": float(np.exp(np.sum(wv * rv) / wv.sum()) * 100.0),
            "covered": float(wv.sum() / tot),
            "n": int(sum(terms[c][1] for c in terms)),
        }
    return out


@pytest.mark.parametrize("drop", [None, {"cc": "01.1.3"}, {"cc": "01.1.1"}])
def test_the_matrix_reproduces_the_level(drop):
    detail: dict = {}
    out = aggregate._basket_levels(_cells(drop), TAX, W0, detail).set_index("country")
    assert set(detail) == set(COUNTRIES)

    # `rel` is shipped at 6 dp, which is worth about 1e-4 of an index point at
    # these levels. The gate that matters is 0.01, and this is two orders inside
    # it -- but it is not zero, and pretending otherwise would make the test
    # fail on a rounding nobody chose to change.
    got = _reweight(detail, W0)
    for cty in COUNTRIES:
        assert got[cty]["level"] == pytest.approx(
            float(out.loc[cty, "level"]), abs=1e-3)
        assert got[cty]["covered"] == pytest.approx(
            float(out.loc[cty, "covered"]), abs=1e-9)
        assert got[cty]["n"] == int(out.loc[cty, "n_leaves"])


@pytest.mark.parametrize("w", [
    {c: 0.25 for c in CLASSES},                                   # equal
    {"01.1.1": 0.05, "01.1.2": 0.05, "01.1.3": 0.05, "02.1.1": 0.85},
    {"01.1.1": 0.9, "01.1.2": 0.05, "01.1.3": 0.05, "02.1.1": 0.0},
])
def test_the_matrix_reproduces_any_vector_not_only_the_published_one(w):
    """The matrix is shipped so a DIFFERENT vector can be applied to it, which
    is the whole reason it is there. A zeroed category leaves the sum entirely
    rather than entering it at zero -- the build says so of an absent category
    and a slider at the bottom of its track means the same thing."""
    detail: dict = {}
    aggregate._basket_levels(_cells({"cc": "01.1.3"}), TAX, W0, detail)
    server = aggregate._basket_levels(
        _cells({"cc": "01.1.3"}), TAX, w).set_index("country")
    got = _reweight(detail, w)
    for cty in COUNTRIES:
        assert got[cty]["level"] == pytest.approx(
            float(server.loc[cty, "level"]), abs=1e-3)
        assert got[cty]["covered"] == pytest.approx(
            float(server.loc[cty, "covered"]), abs=1e-9)


def test_no_matrix_on_the_unweighted_path():
    """With no weight vector the level is a mean over the DIVISIONS, not a
    weighted sum over classes -- there is no vector for a slider to move and no
    matrix that would reconstruct it, so none is shipped."""
    detail: dict = {}
    aggregate._basket_levels(_cells(), TAX, None, detail)
    assert detail == {}


def test_the_gate_splits_into_a_corpus_half_and_a_coverage_half():
    """`ok` is unchanged; `gate` is `ok` with coverage taken back out. Only the
    second half can move when a reader re-weights the basket, and a client with
    only `ok` has no way to re-decide it."""
    from prices.explorer.sources import MIN_BASKET_WEIGHT_COVERED

    out = aggregate._basket_levels(
        _cells({"cc": "01.1.1", "dd": "01.1.3"}), TAX, W0).set_index("country")
    assert set(out.columns) >= {"gate", "ok", "covered"}
    # cc prices no cereals: 0.55 of the vector, under the floor.
    assert float(out.loc["cc", "covered"]) == pytest.approx(0.55)
    assert float(out.loc["cc", "covered"]) < MIN_BASKET_WEIGHT_COVERED
    assert not bool(out.loc["cc", "ok"])
    # ...but it is only coverage that stops it, which is what `gate` says.
    assert bool(out.loc["cc", "gate"])
    # dd loses a lighter category and stays over the floor, so both agree.
    assert bool(out.loc["dd", "ok"]) == bool(out.loc["dd", "gate"])


# ---------------------------------------------------------------- the vectors
def _modes(n_priced=None):
    """The mode set, optionally pretending only the first `n_priced` of ICP's
    categories carry a price -- which is the real corpus's situation, not a
    hypothetical: it prices twelve of the twenty-one."""
    tax = _real_tax()
    icp, meta = weights_mod.default_weights(tax, BASKET_WEIGHT_LEVEL)
    if not icp:
        pytest.skip("no expenditure_weights.csv on this box")
    priced = set(icp) if n_priced is None else set(sorted(icp)[:n_priced])
    return icp, priced, aggregate._weight_modes(tax, icp, meta, priced)


def test_every_mode_is_a_share_of_something():
    icp, _, modes = _modes()
    assert set(modes) >= {"equal", "icp"}
    for k, m in modes.items():
        assert sum(m["w"].values()) == pytest.approx(1.0, abs=2e-5), k
        assert all(v > 0 for v in m["w"].values()), k
        # every mode's categories come out of the published universe, so a
        # slider drawn for one of them is a slider the matrix can answer
        assert set(m["w"]) <= set(icp), k


def test_equal_is_spread_over_what_the_build_can_price():
    """The obvious design -- one vote per category ICP publishes -- ranks NOBODY
    on the real corpus, because nine of ICP's 21 categories carry no price
    anywhere in it and a flat vector puts 43% of every basket on them. Coverage
    then fails for a hole no country could fill, which is precisely what the
    gate is supposed to distinguish itself from."""
    icp, priced, modes = _modes(n_priced=12)
    assert set(modes["equal"]["w"]) == priced
    assert modes["equal"]["meta"]["unpriced"] == pytest.approx(0.0)
    assert sum(modes["equal"]["w"].values()) == pytest.approx(1.0, abs=2e-5)
    # ...whereas an external vector keeps the categories its publisher publishes,
    # and pays for it in coverage rather than in a redefinition
    assert set(modes["icp"]["w"]) == set(icp)
    assert modes["icp"]["meta"]["unpriced"] > 0


def test_every_vector_says_how_much_of_it_cannot_be_priced():
    """`unpriced` is the ceiling on anybody's coverage under that vector. Two
    modes can rank different numbers of countries without differing on a single
    price, and this is the only field that explains it."""
    _, priced, modes = _modes(n_priced=12)
    for k, m in modes.items():
        w, meta = m["w"], m["meta"]
        assert meta["unpriced"] == pytest.approx(
            1.0 - sum(v for c, v in w.items() if c in priced), abs=1e-3), k
        assert meta["n_priced"] <= len(w)
    # the flat vector is defined over what can be priced, so nothing is stranded
    assert modes["equal"]["meta"]["unpriced"] == pytest.approx(0.0)
    # the external ones are not, and pay the difference in coverage
    assert modes["icp"]["meta"]["unpriced"] > 0.05


def test_the_published_vector_is_the_icp_one_untouched():
    """`w0` and the ICP mode are the same numbers. The level in the parquet was
    built with `w0`, so anything else under the "World Bank" button would put a
    published figure behind an unpublished vector."""
    icp, _, modes = _modes()
    assert modes["icp"]["w"] == {k: round(v, 6) for k, v in sorted(icp.items())}


def test_the_imf_vector_is_flat_inside_a_division():
    """WGT_PT publishes at CP01..CP12 and no deeper, so the IMF mode sets the
    food versus alcohol-and-tobacco split and nothing under it. This is the
    caveat the UI has to state; pinning it here is what stops the statement and
    the vector from drifting apart."""
    _, _, modes = _modes()
    if "imf" not in modes:
        pytest.skip("no imf_wgt_pt rows in the weights table")
    w = modes["imf"]["w"]
    by_div: dict[str, set[float]] = {}
    for code, v in w.items():
        by_div.setdefault(code[:2], set()).add(round(v, 6))
    for div, vals in by_div.items():
        assert len(vals) == 1, f"division {div} is not flat: {vals}"
    assert modes["imf"]["meta"]["sourced_depth"] == 1
    assert "DIVISION" in modes["imf"]["meta"]["note"].upper()


def test_a_source_with_no_rows_is_omitted_rather_than_invented(monkeypatch, tmp_path):
    csv_path = tmp_path / "w.csv"
    csv_path.write_text("iso3,code,value,round,source\nXXX,01.1.1,1,2021,icp\n")
    monkeypatch.setattr(weights_mod, "WEIGHTS_CSV", csv_path)
    tax = _real_tax()
    imf, _ = weights_mod.default_weights(
        tax, BASKET_WEIGHT_LEVEL, source="imf_wgt_pt", universe={"01.1.1"})
    assert imf == {}


def test_equal_is_not_the_unweighted_path():
    """Worth stating out loud, because the button says "Equal" and the code path
    it is NOT is also called equal. `weights=None` folds all the way to the
    divisions; equal-per-class stops at the weighted level. The two differ
    whenever a division's classes are unevenly branched, and they are here."""
    eq, _ = weights_mod.equal_weights(CLASSES)
    cells = _cells()
    flat = aggregate._basket_levels(cells, TAX, None).set_index("country")
    per_class = aggregate._basket_levels(cells, TAX, eq).set_index("country")
    assert float(flat.loc["aa", "level"]) != pytest.approx(
        float(per_class.loc["aa", "level"]), rel=1e-6)


def _real_tax() -> dict:
    from prices.explorer.sources import load_taxonomy

    return load_taxonomy()


# ---------------------------------------------------------------- the payload
def test_the_payload_carries_the_matrix_and_the_modes(monkeypatch):
    """End to end through `build_payload`: the matrix in the payload has to
    reproduce the `level` in the same payload, or the dashboard disagrees with
    itself the moment it is opened."""
    fixed = {"01.1.1": 0.4, "01.1.2": 0.3, "01.1.3": 0.2, "01.1.4": 0.1}
    meta = {"source": "icp", "label": "a fixture", "n_reporting": 3, "level": 3,
            "stat": "median", "rounds": {"2021": 3}, "sourced_depth": 3}

    def fake(tax, level, source="icp", universe=None):
        return (dict(fixed), dict(meta)) if source == "icp" else ({}, {})

    monkeypatch.setattr(aggregate, "default_weights", fake)
    payload = _built(monkeypatch)

    b = payload["basket"]
    assert set(b["cty"]) and set(b["modes"]) == {"equal", "icp"}
    assert b["mode0"] == "icp"
    # the label map names every category a slider will draw, plus what it is
    # grouped under
    for code in b["w0"]:
        assert code in b["lab"] and code.rsplit(".", 1)[0] in b["lab"]

    got = _reweight(b["cty"], b["w0"])
    for slug, m in payload["cty"].items():
        if m["level"] is None:
            continue
        assert got[slug]["level"] == pytest.approx(m["level"], abs=0.05)
        assert m["level_gate"] is not None


def _built(monkeypatch) -> dict:
    from conftest import BUILD_CMETA, TAX_BUILD, _observations

    monkeypatch.setattr(aggregate, "load_taxonomy", lambda: TAX_BUILD)
    monkeypatch.setattr(
        aggregate, "load_country_meta",
        lambda: {k: dict(v, iso3=k.upper()) for k, v in BUILD_CMETA.items()})
    monkeypatch.setattr(aggregate, "load_observations", _observations)
    return aggregate.build_payload()
