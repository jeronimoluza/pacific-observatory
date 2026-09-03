from __future__ import annotations

import pytest

from prices.enrich.declared_unit import parse_declared_unit

pytestmark = pytest.mark.unit


def test_quintal_is_100kg():
    # agmarknet: Rs./Quintal mandi prices. 100x lower unit value than treating
    # the price as per-item is the whole point of the defect this fixes.
    basis, amount, su = parse_declared_unit("quintal (100 kg)")
    assert basis == "mass"
    assert amount == pytest.approx(100.0)
    assert su == "kg"


def test_bare_quintal_without_annotation():
    basis, amount, su = parse_declared_unit("Quintal")
    assert basis == "mass"
    assert amount == pytest.approx(100.0)
    assert su == "kg"


def test_bare_kg():
    basis, amount, su = parse_declared_unit("KG")
    assert basis == "mass"
    assert amount == pytest.approx(1.0)
    assert su == "kg"


def test_bare_kg_lowercase():
    basis, amount, su = parse_declared_unit("kg")
    assert basis == "mass"
    assert amount == pytest.approx(1.0)
    assert su == "kg"


def test_500_g_is_half_a_kilo():
    basis, amount, su = parse_declared_unit("500 G")
    assert basis == "mass"
    assert amount == pytest.approx(0.5)
    assert su == "kg"


def test_90_kg():
    basis, amount, su = parse_declared_unit("90 KG")
    assert basis == "mass"
    assert amount == pytest.approx(90.0)
    assert su == "kg"


def test_glued_number_and_unit():
    basis, amount, su = parse_declared_unit("850g")
    assert basis == "mass"
    assert amount == pytest.approx(0.85)
    assert su == "kg"


def test_liter_word_forms():
    assert parse_declared_unit("1 liter")[1:] == (pytest.approx(1.0), "lt")
    assert parse_declared_unit("2 liter")[1:] == (pytest.approx(2.0), "lt")


def test_nepali_kg_kalimati_market():
    basis, amount, su = parse_declared_unit("के.जी.")
    assert basis == "mass"
    assert amount == pytest.approx(1.0)
    assert su == "kg"


def test_hebrew_units_israel_fetchers():
    # tiv_taam_il/yohananof_il/etc -- "100 grams", bare "kilogram", "1 liter".
    assert parse_declared_unit("100 גרם")[1:] == (pytest.approx(0.1), "kg")
    assert parse_declared_unit("קילוגרם")[1:] == (pytest.approx(1.0), "kg")
    assert parse_declared_unit("1ליטר")[1:] == (pytest.approx(1.0), "lt")
    assert parse_declared_unit('ק"ג')[1:] == (pytest.approx(1.0), "kg")


def test_leading_tolerance_marker_is_stripped():
    basis, amount, su = parse_declared_unit("+-450g")
    assert basis == "mass"
    assert amount == pytest.approx(0.45)
    assert su == "kg"


def test_trailing_punctuation_after_unit_token_is_tolerated():
    # "1 Kg. Granel" ("1 kg, bulk") -- the period after "Kg" is stripped, and
    # the unrecognised trailing word is simply never consulted.
    basis, amount, su = parse_declared_unit("1 Kg. Granel")
    assert basis == "mass"
    assert amount == pytest.approx(1.0)
    assert su == "kg"


@pytest.mark.parametrize(
    "dirty",
    [
        "SLE",
        "SDG",
        "USD/LCU",
        "5000.0",
        "5000",
        "",
        None,
        "each",
        "Unit",
        "unit",
        "un",
        "bundle",
        "יחידה",
        "5 X 79g",
        "25 x 18g",
        "$/bandeja 18 kilos",
        "$/saco 25 kilos",
    ],
)
def test_dirty_or_unrecognised_values_produce_no_unit(dirty):
    assert parse_declared_unit(dirty) == (None, None, None)
