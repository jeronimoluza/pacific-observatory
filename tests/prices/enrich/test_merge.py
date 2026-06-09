import pandas as pd
import pytest

from prices.enrich.stages.merge import compute_unit_value, merge_enrichments
from prices.enrich.stages.prepare import _row_input_dict
from prices.enrich.versioning import input_hash


def test_unit_value_mass():
    assert compute_unit_value(
        price=100.0, basis="mass", amount_value=0.5, count=None, multiplier=None
    ) == pytest.approx(200.0)


def test_unit_value_multipack_volume():
    # 10 x 25cl @ price=50  →  per litre = 50 / (0.25 * 10) = 20.0
    assert compute_unit_value(
        price=50.0, basis="volume", amount_value=0.25, count=None, multiplier=10
    ) == pytest.approx(20.0)


def test_unit_value_count_eggs():
    # 12 eggs @ 60  →  per egg = 5.0
    assert compute_unit_value(
        price=60.0, basis="count", amount_value=None, count=12, multiplier=None
    ) == pytest.approx(5.0)


def test_unit_value_promo_as_paid():
    # "buy 2 get 1 free", paid 100, count=3  →  per unit = 100/3
    assert compute_unit_value(
        price=100.0, basis="count", amount_value=None, count=3, multiplier=None
    ) == pytest.approx(100.0 / 3)


def test_unit_value_item_basis():
    # single item (e.g. a knife) — count=1, multiplier=1, no amount_value
    assert compute_unit_value(
        price=15.0, basis="item", amount_value=None, count=None, multiplier=None
    ) == pytest.approx(15.0)


def test_unit_value_missing_amount_value_for_mass_returns_none():
    assert (
        compute_unit_value(
            price=10.0, basis="mass", amount_value=None, count=None, multiplier=None
        )
        is None
    )


def test_unit_value_missing_price_returns_none():
    assert (
        compute_unit_value(
            price=None, basis="mass", amount_value=1.0, count=None, multiplier=None
        )
        is None
    )


def test_unit_value_nan_inputs_returns_none():
    import math

    assert (
        compute_unit_value(
            price=10.0,
            basis="mass",
            amount_value=math.nan,
            count=None,
            multiplier=None,
        )
        is None
    )


def test_merge_left_joins_and_keeps_unenriched_rows():
    raw = pd.DataFrame(
        [
            {
                "product_name": "Coke 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": 60.0,
            },
            {
                "product_name": "Unknown",
                "category": "",
                "country": "PH",
                "currency": "PHP",
                "price": 10.0,
            },
        ]
    )
    # Build enrichment row keyed on the actual input_hash for the Coke row
    coke_input = _row_input_dict(raw.iloc[0].rename({"product_name": "product_name"}))
    # _row_input_dict uses row["product_name"] directly, so this works
    coke_hash = input_hash(coke_input)
    enriched = pd.DataFrame(
        [
            {
                "input_hash": coke_hash,
                "pricing_basis": "volume",
                "amount_value": 1.0,
                "standard_unit": "lt",
                "count": None,
                "multiplier": None,
                "coicop_code": "01.2.2",
                "sub_label_id": "cola",
                "is_promotion": False,
                "is_bundle": False,
                "is_multipack": False,
                "promo_reason": None,
                "confidence": 0.95,
                "state": "resolved",
            }
        ]
    )
    out = merge_enrichments(raw, enriched, key_recompute=True)
    assert len(out) == 2
    coke = out[out["product_name"] == "Coke 1L"].iloc[0]
    assert coke["state"] == "resolved"
    assert coke["unit_value"] == pytest.approx(60.0)  # 60 / (1.0 * 1 * 1)
    unknown = out[out["product_name"] == "Unknown"].iloc[0]
    assert pd.isna(unknown["state"])
    assert pd.isna(unknown["unit_value"])


def test_merge_coalesces_missing_trust_level_to_high():
    """Legacy enrichments without trust_level must surface as high-trust.

    Pre-decoupling cache rows lack the column entirely, and any NaN that
    survives the merge would silently drop the row from a downstream
    trust filter that uses .isin({"high"}).
    """
    raw = pd.DataFrame(
        [
            {
                "product_name": "Coke 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": 60.0,
            }
        ]
    )
    coke_hash = input_hash(_row_input_dict(raw.iloc[0]))
    enriched = pd.DataFrame(
        [
            {
                "input_hash": coke_hash,
                "pricing_basis": "volume",
                "amount_value": 1.0,
                "standard_unit": "lt",
                "count": None,
                "multiplier": None,
                "coicop_code": "01.2.2",
                "sub_label_id": "cola",
                "is_promotion": False,
                "is_bundle": False,
                "is_multipack": False,
                "promo_reason": None,
                "confidence": 0.95,
                "state": "resolved",
                # trust_level intentionally omitted (legacy row)
            }
        ]
    )
    out = merge_enrichments(raw, enriched, key_recompute=True)
    assert "trust_level" in out.columns
    assert out["trust_level"].iloc[0] == "high"


def test_merge_drops_input_hash_column_from_output():
    raw = pd.DataFrame(
        [
            {
                "product_name": "X",
                "category": "",
                "country": "PH",
                "currency": "PHP",
                "price": 1.0,
            }
        ]
    )
    enriched = pd.DataFrame()
    out = merge_enrichments(raw, enriched, key_recompute=True)
    assert "input_hash" not in out.columns
