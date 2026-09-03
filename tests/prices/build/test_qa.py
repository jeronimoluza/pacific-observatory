from __future__ import annotations

import pandas as pd
import pytest

from prices.build.qa import GATE_COLS, compute_qa
from prices.enrich import uv_gate

pytestmark = pytest.mark.unit


def _frame(rows: list[dict]) -> pd.DataFrame:
    base = {
        "coicop_code": "01.1.1.0.0",
        "pricing_basis": "mass",
        "price_local": 10.0,
        "fx_rate": 1.0,
        "trust_level": "high",
        "trust_uv": "high",
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_pharma_dosage_is_quarantined_not_shipped():
    """The defect this gate exists for.

    `1mg*84` parses a real quantity, so `qa_quantity` passes and the row used to
    ship as trusted at ~$880,000/kg. It must now land in `review_uv_category`,
    which is a category verdict, NOT `review_missing_qty` -- the quantity is
    there, it just is not a net pack weight.
    """
    df = compute_qa(_frame([{"coicop_code": "06.1.1.1", "pricing_basis": "mass"}]))
    assert not bool(df.loc[0, "qa_uv_category"])
    assert bool(df.loc[0, "qa_quantity"])
    assert df.loc[0, "qa_status"] == "review_uv_category"


def test_food_mass_still_ships():
    df = compute_qa(_frame([{"coicop_code": "01.1.4.6.0", "pricing_basis": "mass"}]))
    assert bool(df.loc[0, "qa_uv_category"])
    assert df.loc[0, "qa_status"] == "trusted"


def test_count_basis_is_not_category_gated():
    """`count`/`item` denominators are not mass or volume, so the allow-list has
    no opinion on them; they must pass whatever the leaf."""
    df = compute_qa(_frame([{"coicop_code": "06.1.1.1", "pricing_basis": "count"}]))
    assert bool(df.loc[0, "qa_uv_category"])


def test_missing_coicop_code_denies_a_measured_basis():
    df = compute_qa(_frame([{"coicop_code": None, "pricing_basis": "volume"}]))
    assert not bool(df.loc[0, "qa_uv_category"])


def test_gate_col_is_registered():
    assert "qa_uv_category" in GATE_COLS


def test_vectorised_gate_matches_uv_gate_row_by_row():
    """compute_qa maps over DISTINCT codes for speed; assert that shortcut is
    exactly `uv_gate.gate(code, basis)[0]` across a spread of real inputs."""
    codes = [
        "01.1.4.6.0", "02.1.3.0", "04.5.3.1", "05.6.1.1", "05.6.1.9",
        "06.1.1.1", "07.2.2.4", "13.1.2.0", "13.2.9.1", "08.2.0.0",
        "02.1.2.__parent_fallback__", "13.1.__parent_fallback__", None,
    ]
    bases = ["mass", "volume", "length", "count", "item", None]
    rows = [{"coicop_code": c, "pricing_basis": b} for c in codes for b in bases]
    df = compute_qa(_frame(rows))

    expected = [uv_gate.gate(r["coicop_code"], r["pricing_basis"])[0] for r in rows]
    assert df["qa_uv_category"].tolist() == expected


def _priced(unit, usd, **kw) -> pd.DataFrame:
    return compute_qa(
        _frame(
            [
                {
                    "coicop_code": "01.1.4.6.0",
                    "pricing_basis": "mass",
                    "standard_unit": unit,
                    "unit_value_usd": usd,
                    **kw,
                }
            ]
        )
    )


def test_absolute_band_catches_what_the_relative_gate_cannot():
    """The Slovak 100x shape: trust_uv is "high" because the whole cell moved
    together, so qa_uv_inlier passes and only the absolute band objects."""
    df = _priced("kg", 1528.66)
    assert bool(df.loc[0, "qa_uv_inlier"])
    assert not bool(df.loc[0, "qa_uv_plausible"])
    assert df.loc[0, "qa_status"] == "review_uv_implausible"


def test_band_catches_the_low_side_too():
    """Argentina: a 370g jar of mustard at $0.007/kg costs a quarter of a cent."""
    df = _priced("kg", 0.00692)
    assert df.loc[0, "qa_status"] == "review_uv_implausible"


def test_ordinary_prices_still_ship():
    for unit, usd in (("kg", 7.08), ("lt", 2.5), ("unit", 0.27)):
        assert _priced(unit, usd).loc[0, "qa_status"] == "trusted"


def test_boundaries_are_inclusive():
    for unit, usd in (("kg", 0.05), ("kg", 200.0), ("unit", 0.005), ("unit", 500.0)):
        assert bool(_priced(unit, usd).loc[0, "qa_uv_plausible"])


def test_unscoped_units_pass_through():
    """`item` means no quantity was parsed, so there is no per-unit quantity for
    an absolute band to be about. It must not be judged by one."""
    df = _priced("item", 999999.0)
    assert bool(df.loc[0, "qa_uv_plausible"])


def test_missing_unit_or_value_does_not_fail_the_gate():
    assert bool(_priced(None, 12.0).loc[0, "qa_uv_plausible"])
    assert bool(_priced("kg", None).loc[0, "qa_uv_plausible"])


def test_earlier_gates_still_win_the_status():
    """Precedence: a row that fails BOTH the category gate and the band wears
    the category verdict, because that is the earlier and more specific one."""
    df = _priced("kg", 880000.0, coicop_code="06.1.1.1")
    assert not bool(df.loc[0, "qa_uv_plausible"])
    assert df.loc[0, "qa_status"] == "review_uv_category"


def test_plausible_gate_is_registered():
    assert "qa_uv_plausible" in GATE_COLS
