"""Year-over-year and month-over-month, matched leaf by leaf.

A base-period index is only as stable as the month it was based on, and that
month is one noisy draw of a thin corpus. These measures compare period t with
period t-k directly: nothing accumulates, and there is no base.

The estimator is the unweighted MEAN of the leaves' log changes. There are no
expenditure weights here, so everything is equally weighted, and the mean is
the elementary index that follows -- it is also the only one of the two that
decomposes into each leaf's contribution.
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

from prices.explorer import aggregate, geo  # noqa: E402
from prices.explorer.sources import _levels  # noqa: E402

TAX = {
    "01": {"t": "Food", "p": None, "lvl": 1, "leaf": False},
    "01.1": {"t": "Cereals", "p": "01", "lvl": 2, "leaf": False},
    "01.1.1": {"t": "Rice", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.2": {"t": "Bread", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.3": {"t": "Pasta", "p": "01.1", "lvl": 3, "leaf": True},
    "01.1.4": {"t": "Noodles", "p": "01.1", "lvl": 3, "leaf": True},
}
LEAVES = ["01.1.1", "01.1.2", "01.1.3", "01.1.4"]
# a cell needs MIN_CELL_OBS observations before it exists at all
OBS_PER_CELL = 3


def _exploded(prices: dict) -> pd.DataFrame:
    """prices maps (country, leaf, period) -> unit value in US$."""
    rows = []
    for (country, code, period), usd in prices.items():
        for _ in range(OBS_PER_CELL):
            for node in _levels(code):
                rows.append(
                    {
                        "country": country,
                        "coicop_code": code,
                        "node": node,
                        "standard_unit": "kg",
                        "period": period,
                        "unit_value_usd": usd,
                    }
                )
    return pd.DataFrame(rows)


def test_the_group_change_is_the_mean_of_the_leaves_log_changes():
    """Rice +10%, bread +20% over twelve months.

    The mean of the log changes is (ln 1.1 + ln 1.2)/2 = 0.1388159, so the
    group is +14.891%. The MEDIAN of the same two is identical here by
    construction; the arithmetic mean of +10% and +20% would be +15.000%, and
    the geometric mean of the two prices' ratio is what this is not.
    """
    ex = _exploded(
        {
            ("a", "01.1.1", "2025-01"): 2.00,
            ("a", "01.1.1", "2026-01"): 2.20,
            ("a", "01.1.2", "2025-01"): 4.00,
            ("a", "01.1.2", "2026-01"): 4.80,
        }
    )
    out = aggregate._lagged_changes(ex, TAX).set_index(["node", "lag"])
    expect = (np.log(1.1) + np.log(1.2)) / 2
    assert out.loc[("01.1", 12), "lr"] == pytest.approx(expect)
    assert out.loc[("01.1", 12), "lr"] == pytest.approx(0.13881587, abs=1e-8)
    assert np.expm1(out.loc[("01.1", 12), "lr"]) * 100 == pytest.approx(
        14.8913, abs=1e-4
    )
    assert out.loc[("01.1", 12), "k"] == 2
    assert out.loc[("01", 12), "lr"] == pytest.approx(expect)
    # a leaf is its own basket
    assert out.loc[("01.1.1", 12), "lr"] == pytest.approx(np.log(1.1))
    assert out.loc[("01.1.1", 12), "k"] == 1


def test_only_leaves_priced_in_BOTH_periods_are_counted():
    """A leaf that appears only at t must not enter the average at all."""
    ex = _exploded(
        {
            ("a", "01.1.1", "2025-01"): 2.00,
            ("a", "01.1.1", "2026-01"): 2.20,
            ("a", "01.1.2", "2025-01"): 4.00,
            ("a", "01.1.2", "2026-01"): 4.80,
            # priced once only, and at a wild level: it must be invisible here
            ("a", "01.1.3", "2026-01"): 900.0,
        }
    )
    out = aggregate._lagged_changes(ex, TAX).set_index(["node", "lag"])
    assert out.loc[("01.1", 12), "k"] == 2
    assert out.loc[("01.1", 12), "lr"] == pytest.approx((np.log(1.1) + np.log(1.2)) / 2)


def test_the_lag_is_exact_not_whatever_came_before():
    """Eleven months apart is not a year-over-year change.

    This is the difference from `_chained_index`, which links to the previous
    observation whatever its date and books the whole move onto the later
    period.
    """
    ex = _exploded(
        {
            ("a", "01.1.1", "2025-02"): 2.00,
            ("a", "01.1.1", "2026-01"): 2.20,
        }
    )
    out = aggregate._lagged_changes(ex, TAX)
    assert out.empty, out


def test_every_horizon_is_offered_where_the_data_reaches():
    months = ["2023-%02d" % m for m in range(1, 13)]
    months += ["2024-%02d" % m for m in range(1, 13)]
    months += ["2025-%02d" % m for m in range(1, 13)]
    months += ["2026-%02d" % m for m in range(1, 13)]
    prices = {}
    for i, p in enumerate(months):
        for j, code in enumerate(LEAVES):
            prices[("a", code, p)] = round((2.0 + j) * (1.01**i), 6)
    out = aggregate._lagged_changes(_exploded(prices), TAX)
    got = sorted(out.lag.unique().tolist())
    assert got == [1, 12, 24, 36]
    at = out[(out.node == "01.1") & (out.period == "2026-12")].set_index("lag")
    assert np.expm1(at.loc[1, "lr"]) * 100 == pytest.approx(1.0, abs=1e-4)
    assert np.expm1(at.loc[12, "lr"]) * 100 == pytest.approx(12.6825, abs=1e-3)
    assert np.expm1(at.loc[24, "lr"]) * 100 == pytest.approx(26.9735, abs=1e-3)
    assert np.expm1(at.loc[36, "lr"]) * 100 == pytest.approx(43.0769, abs=1e-3)
    assert at.loc[12, "k"] == 4


def test_a_thin_node_is_gated_exactly_as_the_chain_is():
    """`_link_need` is the one gate, and a leaf needs one matched item."""
    nodes = pd.Series(["01", "01.1", "01.1.1"])
    need = aggregate._link_need(nodes, TAX)
    assert need.tolist() == [2.0, 2.0, 1.0]


# ------------------------------------------------------------------ geo grain


def _geo_exploded():
    """Four countries, four leaves, 30 months, every price compounding at 1%."""
    months = ["2024-%02d" % m for m in range(1, 13)]
    months += ["2025-%02d" % m for m in range(1, 13)]
    months += ["2026-%02d" % m for m in range(1, 7)]
    prices = {}
    for ci, country in enumerate(["aa", "bb", "cc", "dd"]):
        for i, p in enumerate(months):
            for j, code in enumerate(LEAVES):
                prices[(country, code, p)] = round((2.0 + j + ci) * (1.01**i), 6)
    return _exploded(prices)


CMETA = {
    "aa": {"name": "Aa", "region": "R1", "subregion": "S1"},
    "bb": {"name": "Bb", "region": "R1", "subregion": "S1"},
    "cc": {"name": "Cc", "region": "R2", "subregion": "S2"},
    "dd": {"name": "Dd", "region": "R2", "subregion": "S2"},
}


def test_the_geo_series_carry_every_horizon():
    out, _ = geo.build_geo_series(_geo_exploded(), TAX, CMETA)
    key = "M|W|01.1|kg"
    assert key in out, sorted(out)[:10]
    chg = out[key]["chg"]
    assert sorted(int(k) for k in chg) == [1, 12, 24]
    p = out[key]["p"]
    i = p.index("2026-06")
    assert chg["12"]["v"][i] == pytest.approx(12.683, abs=1e-3)
    assert chg["1"]["v"][i] == pytest.approx(1.0, abs=1e-3)
    # sixteen (country, leaf) pairs stand behind the world's aggregate change
    assert chg["12"]["k"][i] == 16


def test_a_quarterly_horizon_is_counted_in_quarters_not_months():
    out, _ = geo.build_geo_series(_geo_exploded(), TAX, CMETA)
    chg = out["Q|W|01.1|kg"]["chg"]
    assert sorted(int(k) for k in chg) == [3, 12, 24]
    p = out["Q|W|01.1|kg"]["p"]
    i = p.index("2026Q2")
    # a quarter's price is the median of its three months, so a year over year
    # at 1% a month is still 1.01^12 - 1
    assert chg["12"]["v"][i] == pytest.approx(12.683, abs=1e-2)
    assert chg["3"]["v"][i] == pytest.approx(3.030, abs=1e-2)


def test_the_measure_exists_at_every_geography_the_gates_allow():
    """World, region and subregion all carry it; the country grain does not.

    At a country geo an "item" is a (country, leaf) pair, so a country holds
    one pair per leaf -- four here, under GEO_MIN_LINK_PAIRS. That gate is
    pre-existing and applies to `_chain` identically; the country-grain change
    is published from `aggregate._lagged_changes` instead, which counts leaves
    rather than pairs.
    """
    out, geos = geo.build_geo_series(_geo_exploded(), TAX, CMETA)
    kinds = {geos[k.split("|")[1]]["kind"] for k in out if k.startswith("M|")}
    assert {"world", "region", "subregion"} <= kinds
    assert out["M|R:R1|01.1|kg"]["chg"]["12"]["k"][-1] == 8


# ------------------------------------------------------------- whole payload


def _observations() -> pd.DataFrame:
    """A corpus dense enough to clear every gate the build applies."""
    months = ["2024-%02d" % m for m in range(1, 13)]
    months += ["2025-%02d" % m for m in range(1, 13)]
    months += ["2026-%02d" % m for m in range(1, 7)]
    rows = []
    for ci, country in enumerate(CMETA):
        for i, p in enumerate(months):
            for j, code in enumerate(LEAVES):
                for _ in range(OBS_PER_CELL):
                    rows.append(
                        {
                            "country": country,
                            "currency": "USD",
                            "source": "shop%d" % (ci % 2),
                            "observation_date": pd.Timestamp(p + "-15"),
                            "coicop_code": code,
                            "pricing_basis": "retail",
                            "standard_unit": "kg",
                            "unit_value_local": (2.0 + j + ci) * (1.01**i),
                            "unit_value_usd": (2.0 + j + ci) * (1.01**i),
                            "mass_source": "declared",
                            "qa_status": "trusted",
                            "product_name": "thing",
                            "fx_rate": 1.0,
                        }
                    )
    df = pd.DataFrame(rows)
    df["is_modelled"] = False
    df["is_derived"] = False
    df["period"] = df.observation_date.dt.to_period("M").astype(str)
    return df


@pytest.fixture
def built(monkeypatch):
    monkeypatch.setattr(aggregate, "load_taxonomy", lambda: TAX)
    monkeypatch.setattr(
        aggregate,
        "load_country_meta",
        lambda: {k: dict(v, iso3=k.upper()) for k, v in CMETA.items()},
    )
    monkeypatch.setattr(aggregate, "load_observations", _observations)
    return aggregate.build_payload()


def test_the_payload_carries_a_populated_changes_block(built):
    assert built["changes"], "no country-grain changes were emitted"
    node_pos = {n: i for i, n in enumerate(built["nodeIdx"])}
    cty_pos = {c: i for i, c in enumerate(built["ctyIdx"])}
    key = "%d|%d|0" % (cty_pos["aa"], node_pos["01.1"])
    entry = built["changes"][key]
    assert sorted(int(k) for k in entry) == [1, 12, 24]
    i = entry["12"]["p"].index("2026-06")
    assert entry["12"]["v"][i] == pytest.approx(12.683, abs=1e-2)
    assert entry["12"]["k"][i] == 4
    assert entry["1"]["v"][i] == pytest.approx(1.0, abs=1e-2)


def test_the_world_series_carry_the_same_horizons(built):
    node_pos = {n: i for i, n in enumerate(built["nodeIdx"])}
    key = "M|W|%d|0" % node_pos["01.1"]
    chg = built["gseries"][key]["chg"]
    i = built["gseries"][key]["p"].index("2026-06")
    assert chg["12"]["v"][i] == pytest.approx(12.683, abs=1e-2)
    assert chg["12"]["k"][i] == 16


def test_the_base_100_chain_still_ships_alongside(built):
    """Retiring base-100 as the DEFAULT does not delete it."""
    node_pos = {n: i for i, n in enumerate(built["nodeIdx"])}
    key = "M|W|%d|0" % node_pos["01.1"]
    assert any(v is not None for v in built["gseries"][key]["idx"])
