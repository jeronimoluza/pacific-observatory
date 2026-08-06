from __future__ import annotations

import pytest

from prices.enrich.stages.classify import _structural_fields

pytestmark = pytest.mark.unit


def test_details_ignored_when_name_has_quantity():
    # Name already resolves a quantity -> details must not override it.
    sf = _structural_fields(
        "Goodday Full Cream Milk 1L", None, "singapore", "en", details="500 ml"
    )
    assert sf["pricing_basis"] == "volume"
    assert sf["amount_value"] == 1.0


def test_details_supplies_mass_when_name_is_itemless():
    # pickaroo shape: token-less name, size lives in details.
    sf = _structural_fields(
        "Maggi Oyster Sauce", None, "philippines", "en", details="~500 g"
    )
    assert sf["pricing_basis"] == "mass"
    assert sf["amount_value"] == 0.5
    assert sf["standard_unit"] == "kg"


def test_details_supplies_count_when_name_is_itemless():
    sf = _structural_fields(
        "Bounty Fresh Large Premium Eggs", None, "philippines", "en", details="10 pcs"
    )
    assert sf["pricing_basis"] == "count"
    assert sf["count"] == 10


def test_itemlike_details_stay_item():
    # "1 pc" / "1 pack" carry no resolvable quantity -> row stays item.
    sf = _structural_fields(
        "Sun Flower Bouquet 3 Stem", None, "philippines", "en", details="1 bouquet"
    )
    assert sf["pricing_basis"] == "item"


def test_no_details_is_unchanged_behavior():
    # Backward-compat: absent details -> same as before the fallback existed.
    sf = _structural_fields(
        "Maggi Oyster Sauce", None, "philippines", "en", details=None
    )
    assert sf["pricing_basis"] == "item"
    sf_empty = _structural_fields(
        "Maggi Oyster Sauce", None, "philippines", "en", details=""
    )
    assert sf_empty["pricing_basis"] == "item"
