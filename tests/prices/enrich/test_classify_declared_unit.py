from __future__ import annotations

import pytest

from prices.enrich.stages.classify import _structural_fields

pytestmark = pytest.mark.unit


def test_declared_unit_resolves_an_itemless_name():
    # agmarknet: "Ajwan" has no quantity token; the fetcher declares the
    # price is Rs./Quintal. Bug: this used to stay pricing_basis="item".
    sf = _structural_fields(
        "Ajwan", None, "india", "en", details=None, unit="quintal (100 kg)"
    )
    assert sf["pricing_basis"] == "mass"
    assert sf["amount_value"] == pytest.approx(100.0)
    assert sf["standard_unit"] == "kg"
    assert sf["unit_declared"] is True


def test_declared_kg_resolves_bread():
    sf = _structural_fields("Bread", None, "afghanistan", "en", unit="KG")
    assert sf["pricing_basis"] == "mass"
    assert sf["amount_value"] == pytest.approx(1.0)
    assert sf["standard_unit"] == "kg"
    assert sf["unit_declared"] is True


def test_name_extracted_quantity_wins_over_declared_unit():
    # A per-row regex match on the name is more specific than a source-level
    # sale-unit declaration -- the declared unit must never override it.
    sf = _structural_fields(
        "Goodday Full Cream Milk 1L", None, "singapore", "en", unit="KG"
    )
    assert sf["pricing_basis"] == "volume"
    assert sf["amount_value"] == pytest.approx(1.0)
    assert sf["unit_declared"] is False


def test_details_fallback_still_wins_over_declared_unit():
    # details (a per-row size string) is tried before the declared unit.
    sf = _structural_fields(
        "Maggi Oyster Sauce", None, "philippines", "en", details="~500 g", unit="L"
    )
    assert sf["pricing_basis"] == "mass"
    assert sf["amount_value"] == pytest.approx(0.5)
    assert sf["unit_declared"] is False


def test_dirty_declared_unit_does_not_change_anything():
    sf = _structural_fields("Ajwan", None, "india", "en", unit="SLE")
    assert sf["pricing_basis"] == "item"
    assert sf["unit_declared"] is False


def test_no_declared_unit_is_unchanged_behavior():
    sf = _structural_fields("Ajwan", None, "india", "en", unit=None)
    assert sf["pricing_basis"] == "item"
    assert sf["unit_declared"] is False
