from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

# Pre-existing, unrelated environment gap: src/prices/enrich/stages/prepare.py
# (committed since da1667b2, 2026-07-14) imports prices.enrich.boilerplate,
# which does not exist in this worktree, breaking the whole aggregate.py
# import chain (also breaks tests/prices/enrich/test_prepare.py). Stub it
# here only, so this test file can exercise the real aggregate module.
if "prices.enrich.boilerplate" not in sys.modules:
    _stub = types.ModuleType("prices.enrich.boilerplate")
    _stub.strip_boilerplate = lambda name: name
    sys.modules["prices.enrich.boilerplate"] = _stub

from prices.build import aggregate

pytestmark = pytest.mark.unit


def _fake_cache_rows() -> pd.DataFrame:
    base = {
        "country": "testland",
        "currency": "USD",
        "coicop_code": "01.1.1.0.0",
        "sub_label_id": "sub_1",
        "taxonomy_version": aggregate.TAXONOMY_VERSION,
        "state": "resolved",
        "pricing_basis": "mass",
        "amount_value": 0.5,
        "standard_unit": "kg",
        "count": 1,
        "multiplier": 1,
        "is_promotion": False,
        "is_bundle": False,
        "is_multipack": False,
        "confidence": 0.9,
    }
    rows = [
        {**base, "product_name_original": "prod_high", "trust_level": "high",
         "created_at": pd.Timestamp("2026-01-01")},
        {**base, "product_name_original": "prod_low", "trust_level": "low",
         "created_at": pd.Timestamp("2026-01-02")},
        {**base, "product_name_original": "prod_flagged", "trust_level": "flagged",
         "created_at": pd.Timestamp("2026-01-03")},
        {**base, "product_name_original": "prod_missing", "trust_level": None,
         "created_at": pd.Timestamp("2026-01-04")},
    ]
    return pd.DataFrame(rows)


def test_load_filtered_cache_excludes_non_high_trust(monkeypatch):
    monkeypatch.setattr(aggregate.enrich_cache, "read_cache", _fake_cache_rows)
    monkeypatch.setattr(aggregate, "EAP_COUNTRIES", frozenset({"testland"}))
    monkeypatch.setattr(aggregate, "FNB_COICOP_PREFIXES", ("01.",))

    out = aggregate.load_filtered_cache()

    assert set(out["product_name_original"]) == {"prod_high", "prod_missing"}
    assert set(out["trust_level"]) == {"high"}


def test_compute_unit_values_never_sees_non_high_trust(monkeypatch):
    monkeypatch.setattr(aggregate.enrich_cache, "read_cache", _fake_cache_rows)
    monkeypatch.setattr(aggregate, "EAP_COUNTRIES", frozenset({"testland"}))
    monkeypatch.setattr(aggregate, "FNB_COICOP_PREFIXES", ("01.",))

    cache = aggregate.load_filtered_cache()
    # In the real pipeline, `price` arrives from the products_input/raw-CSV
    # side of the join, not from cache (not in CACHE_KEEP_COLS) — attach it
    # here to simulate the post-join frame that _compute_unit_values expects.
    cache = cache.assign(price=10.0)
    result = aggregate._compute_unit_values(cache)

    assert "prod_low" not in set(result["product_name_original"])
    assert "prod_flagged" not in set(result["product_name_original"])
    assert set(result["product_name_original"]) == {"prod_high", "prod_missing"}
    assert result["unit_value_local"].notna().all()
