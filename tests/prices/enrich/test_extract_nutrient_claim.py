"""Nutritional gram-CLAIMS are not pack sizes.

Supplement names advertise a serving's nutrient content in the same
`<number><gram unit>` shape a pack size uses ("24g Protein Per Serving",
"5g Creatine"). Read as the package quantity, a 2 lb tub of whey priced as a
24 g sachet — a unit value ~80x too high.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract

pytestmark = pytest.mark.unit


def _ex(name, lang="en"):
    return extract(name, None, "", lang)


@pytest.mark.parametrize(
    "name",
    [
        "Optimum Nutrition Gold Standard Whey 24g Protein Per Serving",
        "MuscleTech Whey Protein 25g Protein per scoop",
        "Bulk Pure Creatine 5g Creatine per serving",
        "Applied Nutrition BCAA 7g BCAA",
        "Ronnie Coleman Pre-Workout 3g Beta Alanine",
    ],
)
def test_a_nutrient_claim_is_never_the_pack_size(name):
    sf = _ex(name)
    assert sf.pricing_basis != "mass"
    assert sf.amount_value is None


def test_the_real_pack_size_after_the_claim_is_recovered():
    """The claim shadows a genuine measure that follows it; suppressing the
    claim has to re-scan, or the row loses its quantity entirely."""
    sf = _ex("Optimum Nutrition Gold Standard Whey 24g Protein Per Serving 2lb")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.907184, rel=1e-6)


def test_a_pack_size_stated_before_the_claim_is_untouched():
    sf = _ex("Optimum Nutrition Gold Standard Whey 2kg 24g Protein Per Serving")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(2.0)


@pytest.mark.parametrize(
    "name, expected_av",
    [
        # A real pack size adjacent to a nutrient word: too big to be a serving
        # claim, so it stays the quantity.
        ("Whey Protein 900g Chocolate", 0.9),
        ("Dymatize ISO 100 Whey Protein Isolate 5lb", 2.26796),
        # No nutrient word and no per-serving phrase anywhere near the measure.
        ("Nature Valley Protein Bar 60g", 0.06),
        # A grocery noun that is also a nutrient states its own pack size in the
        # leading shape, so only supplement product nouns may lead.
        ("Tate & Lyle Sugar Sticks 5g", 0.005),
        ("Kellogg's All-Bran High Fibre 45g", 0.045),
    ],
)
def test_genuine_supplement_pack_sizes_survive(name, expected_av):
    sf = _ex(name)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)


def test_an_ordinary_grocery_gram_figure_is_untouched():
    sf = _ex("Anchor Cheddar Cheese Slices 24g")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.024)
