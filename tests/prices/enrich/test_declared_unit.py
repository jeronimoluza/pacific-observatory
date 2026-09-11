from __future__ import annotations

import pytest

from prices.enrich.declared_unit import parse_declared_unit
from prices.enrich.stages.merge import compute_unit_value

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


# ---------------------------------------------------------------------------
# WFP VAM sale units. Every case below is a verbatim row from
# data/prices/**/wfp_prices/price_observations.csv (68 countries, 118,036
# rows), whose `unit` column is free text. The commodity name carries no
# quantity token ("Sugar", "Maize (yellow)"), so `unit` is the only quantity
# signal those rows have.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "country,item,unit,expected_basis,expected_amount,expected_su",
    [
        # lac/central_america/nicaragua -- wfp_nic, "Sugar", 0.37 USD/Pound.
        ("Nicaragua", "Sugar", "Pound", "mass", 0.453592, "kg"),
        # lac/central_america/el_salvador -- wfp_slv, "Beans (red)", 0.58 USD.
        ("El Salvador", "Beans (red)", "Libra", "mass", 0.453592, "kg"),
        # lac/central_america/guatemala -- wfp_gtm, "Maize (yellow)", 132.5 GTQ
        # per hundredweight.
        ("Guatemala", "Maize (yellow)", "100 Pounds", "mass", 45.3592, "kg"),
        # ssa/west_africa/liberia -- wfp_lbr, "Fuel (diesel)", 844.3858 LRD.
        # Liberia, Haiti, Guatemala and Colombia are the only countries that
        # write a bare "Gallon", and all four are US-gallon jurisdictions; the
        # one imperial-gallon source in the corpus (ky_ofreg_fuel) spells it
        # "imperial_gallon".
        ("Liberia", "Fuel (diesel)", "Gallon", "volume", 3.785411784, "lt"),
        # menaap/middle_east/west_bank_and_gaza -- wfp_pse, "Water (drinking)",
        # 2.874 ILS.
        (
            "State of Palestine",
            "Water (drinking)",
            "Cubic meter",
            "volume",
            1000.0,
            "lt",
        ),
        # ssa/east_africa/ethiopia -- wfp_eth, "Maize (white)", 1231.7797 ETB.
        # Regression: the "<number> <unit>" shape already worked.
        ("Ethiopia", "Maize (white)", "100 KG", "mass", 100.0, "kg"),
    ],
)
def test_wfp_sale_units(
    country, item, unit, expected_basis, expected_amount, expected_su
):
    basis, amount, su = parse_declared_unit(unit)
    assert basis == expected_basis, f"{country}/{item}"
    assert amount == pytest.approx(expected_amount), f"{country}/{item}"
    assert su == expected_su, f"{country}/{item}"


def test_wfp_pound_row_prices_per_kilo():
    """End-to-end: wfp_nic "Sugar" at 0.37 USD/Pound is 0.82 USD/kg."""
    basis, amount, su = parse_declared_unit("Pound")
    uv = compute_unit_value(0.37, basis, amount, None, None)
    assert su == "kg"
    assert uv == pytest.approx(0.37 / 0.453592)


@pytest.mark.parametrize(
    "unit",
    [
        # Not goods at all -- converting any of these would put an exchange
        # rate, a wage or a transport fare into the price-per-kg grid.
        "USD/LCU",  # wfp_som/ssd/afg/yem "Exchange rate"
        "Day",  # "Wage (non-qualified labour)"
        "Month",  # wfp_col "Wage (non-qualified labour, non-agricultural)"
        "Course",  # wfp_cod/syr "Transport (public, bus)"
        "1 GB",  # wfp_syr "Internet bundle"
        "LCU/3.5kg",  # wfp_ssd "Milling cost (sorghum)" -- a tariff, not a pack
        # Countable: parse_declared_unit has no `count` slot, and
        # compute_unit_value divides count/item rows by `count`, never by
        # `amount_value`. Folding these in would price a dozen as one piece.
        "Head",  # "Livestock (cattle)"
        "10 pcs",
        "Dozen",
        "1 piece",
        "Loaf",
        "Bunch",
        # Container units whose size is commodity-dependent.
        "Marmite",  # Haiti; 2.7 kg for rice, different for beans
        "Sack",
        "Heap",
        "Cuartilla",
        "Tin (20 L)",
        # "gals" is deliberately absent: _NUM_UNIT_RE reads "1,000" as 1.0.
        "1,000 gals",
    ],
)
def test_wfp_units_that_must_not_convert(unit):
    assert parse_declared_unit(unit) == (None, None, None)
