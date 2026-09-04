"""`oz` on an alcoholic drink is a FLUID ounce, not a weight one.

`extract` has no leaf to read, so it maps every `oz` through the mass table: a
12 fl oz beer is filed as 340 g and priced per kilogram, in a division whose
every other row is priced per litre. The leaf IS known in `decide_rows`, which
is where the reading gets corrected.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich.stages.classify import decide_rows

pytestmark = pytest.mark.unit

NAME_KEY = ("product_name_original",)


def _products(names):
    n = len(names)
    return pd.DataFrame(
        {
            "input_hash": [f"h{i}" for i in range(n)],
            "product_name_original": names,
            "category": [None] * n,
            "country": ["usa"] * n,
            "lang": ["en"] * n,
            "details": [None] * n,
            "declared_coicop_codes": [None] * n,
        }
    )


def _decide(names, leaves):
    scored = {(n,): (leaf, 0.99, True, leaf, 0.97) for n, leaf in zip(names, leaves)}
    return decide_rows(_products(names), scored, NAME_KEY, frozenset())


def test_fluid_oz_on_an_alcoholic_drink_becomes_volume():
    names = ["Budweiser Lager Beer 12 oz Bottle", "Heineken 11.2 oz Can"]
    out = _decide(names, ["02.1.3.0", "02.1.3.0"])
    assert list(out["pricing_basis"]) == ["volume", "volume"]
    assert list(out["standard_unit"]) == ["lt", "lt"]
    assert out.loc[0, "amount_value"] == pytest.approx(12 * 0.0295735)
    assert out.loc[1, "amount_value"] == pytest.approx(11.2 * 0.0295735)


def test_a_metric_alcohol_row_is_untouched():
    out = _decide(["Corona Extra Beer 355ml"], ["02.1.3.0"])
    assert out.loc[0, "pricing_basis"] == "volume"
    assert out.loc[0, "amount_value"] == pytest.approx(0.355)


def test_ounces_outside_the_alcohol_division_stay_mass():
    """The claim is about beverages, not about the token: 12 oz of coffee beans
    really is a weight."""
    out = _decide(["Starbucks Pike Place Ground Coffee 12 oz"], ["01.2.1.1"])
    assert out.loc[0, "pricing_basis"] == "mass"
    assert out.loc[0, "standard_unit"] == "kg"
    assert out.loc[0, "amount_value"] == pytest.approx(12 * 0.0283495)


def test_an_alcohol_row_with_no_ounce_measure_is_untouched():
    out = _decide(["Jack Daniel's Old No. 7 Whiskey 750ml"], ["02.1.2.0"])
    assert out.loc[0, "pricing_basis"] == "volume"
    assert out.loc[0, "amount_value"] == pytest.approx(0.75)
