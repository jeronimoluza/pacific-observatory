import pandas as pd
import pytest

from prices.enrich.stages.prepare import parse_price, prepare_input
from prices.enrich.versioning import input_hash


def test_parse_price_us_format():
    assert parse_price("$1,250.00", "USD") == pytest.approx(1250.0)


def test_parse_price_eu_format():
    assert parse_price("1.250,00 €", "EUR") == pytest.approx(1250.0)


def test_parse_price_idr_format():
    # Legacy parse_price handled IDR specially — preserve that.
    assert parse_price("Rp 27.000", "IDR") == pytest.approx(27000.0)
    assert parse_price("Rp 1.234.567,50", "IDR") == pytest.approx(1234567.50)


def test_parse_price_numeric_passthrough():
    assert parse_price(42.5, "USD") == pytest.approx(42.5)
    assert parse_price(100, "USD") == pytest.approx(100.0)


def test_parse_price_empty_and_invalid():
    assert parse_price(None, "USD") is None
    assert parse_price("", "USD") is None
    assert parse_price("not a price", "USD") is None


def test_prepare_dedups_on_input_hash():
    raw = pd.DataFrame(
        [
            {
                "product_name": "Coke 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": "60.00",
            },
            {
                "product_name": "Coke 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": "60.00",
            },
            {
                "product_name": "Pepsi 1L",
                "category": "Drinks",
                "country": "PH",
                "currency": "PHP",
                "price": "55.00",
            },
        ]
    )
    out = prepare_input(raw)
    assert len(out) == 2
    assert set(out.columns) >= {
        "input_hash",
        "product_name_original",
        "category",
        "country",
        "currency",
        "price",
        "n_rows",
    }
    coke = out[out["product_name_original"] == "Coke 1L"].iloc[0]
    assert coke["n_rows"] == 2
    assert coke["input_hash"] == input_hash(
        {
            "product_name_original": "Coke 1L",
            "category": "Drinks",
            "country": "PH",
            "currency": "PHP",
        }
    )
