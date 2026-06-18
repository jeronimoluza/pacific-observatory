"""Tests for the prices.enrich.stages.enrich match cascade.

Pure-function `cascade()` is exercised directly (no LLM, no I/O):
  * Tier 0 — input_hash hit propagates payload to sibling hashes in product
  * Tier 1 — product_identity_key hit
  * Tier 2 — (canonical_loose, country) hit (cross-pack-size)
  * Tier 4 — residual products with no cache match fall through
  * match_log row written per resolved product with correct match_method
  * cache.append_enrichments skipped for input_hashes already cached
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich.extract import StructuralFields
from prices.enrich.stages.enrich import (
    _overlay_tier_a,
    _pricing_basis_mismatch,
    cascade,
)


def _product(
    pid: str,
    loose: str,
    country: str,
    first_name: str,
    input_hashes: list[str],
    currency: str = "PHP",
    category: str = "beverage",
) -> dict:
    return {
        "product_identity_key": pid,
        "canonical_loose": loose,
        "country": country,
        "lang": "en",
        "brand": "",
        "count": None,
        "value": None,
        "unit": "",
        "category": category,
        "currency": currency,
        "first_name": first_name,
        "price": 50.0,
        "n_observations": len(input_hashes),
        "n_input_hashes": len(input_hashes),
        "input_hashes": input_hashes,
    }


def _cached(
    input_hash: str,
    pid: str = "",
    loose: str = "",
    country: str = "philippines",
    coicop_code: str = "01.2.2",
    sub_label_id: str = "soft-drink",
    pricing_basis: str = "volume",
) -> dict:
    return {
        "input_hash": input_hash,
        "product_identity_key": pid,
        "canonical_loose": loose,
        "country": country,
        "pricing_basis": pricing_basis,
        "amount_value": 1.0,
        "standard_unit": "lt",
        "count": 1,
        "multiplier": None,
        "dimensions_json": "[]",
        "coicop_code": coicop_code,
        "sub_label_id": sub_label_id,
        "is_promotion": False,
        "is_bundle": False,
        "is_multipack": False,
        "promo_reason": None,
        "confidence": 0.95,
        "state": "resolved",
        "raw_response_text": "",
        "total_tokens": 0,
        "model_version": "gemini-test",
    }


@pytest.fixture
def fixture_50():
    """50 products: 10 tier-0, 10 tier-1, 10 tier-2, 20 residual."""
    products: list[dict] = []
    cached_rows: list[dict] = []

    # Tier 0: input_hash hit. Two input_hashes per product, one cached.
    for i in range(10):
        h_cached = f"t0_cached_{i}"
        h_new = f"t0_new_{i}"
        products.append(
            _product(
                pid=f"t0_pid_{i}",
                loose=f"t0_loose_{i}",
                country="philippines",
                first_name=f"Coke {i}L",
                input_hashes=[h_cached, h_new],
            )
        )
        cached_rows.append(_cached(h_cached))

    # Tier 1: product_identity_key hit. Two input_hashes per product, neither cached.
    for i in range(10):
        pid = f"t1_pid_{i}"
        products.append(
            _product(
                pid=pid,
                loose=f"t1_loose_{i}",
                country="australia",
                first_name=f"Heinz {i}",
                input_hashes=[f"t1_a_{i}", f"t1_b_{i}"],
                currency="AUD",
                category="condiment",
            )
        )
        cached_rows.append(_cached(f"t1_other_{i}", pid=pid, country="australia"))

    # Tier 2: (canonical_loose, country) hit. Cached row has different input_hash and pid.
    for i in range(10):
        loose = f"t2_loose_{i}"
        products.append(
            _product(
                pid=f"t2_pid_{i}",
                loose=loose,
                country="malaysia",
                first_name=f"Milo {i}",
                input_hashes=[f"t2_x_{i}"],
                currency="MYR",
            )
        )
        cached_rows.append(
            _cached(
                f"t2_other_{i}",
                pid=f"t2_otherpid_{i}",
                loose=loose,
                country="malaysia",
            )
        )

    # Residual: no overlap with cache.
    for i in range(20):
        products.append(
            _product(
                pid=f"r_pid_{i}",
                loose=f"r_loose_{i}",
                country="vietnam",
                first_name=f"Misc {i}",
                input_hashes=[f"r_{i}"],
                currency="VND",
            )
        )
    return pd.DataFrame(products), pd.DataFrame(cached_rows)


def test_cascade_partitions_products_across_tiers(fixture_50):
    products, cached = fixture_50
    cache_rows, residual, log, _cross_check = cascade(products, cached)
    methods = [r["match_method"] for r in log]
    # tier-a runs unconditionally on non-empty first_name → "+regex" suffix.
    assert sum(1 for m in methods if m.startswith("input_hash")) == 10
    assert sum(1 for m in methods if m.startswith("product_identity_key")) == 10
    assert sum(1 for m in methods if m.startswith("canonical_loose")) == 10
    assert len(residual) == 20


def test_cascade_residual_keeps_full_row_shape(fixture_50):
    products, cached = fixture_50
    _, residual, _, _cross_check = cascade(products, cached)
    assert "input_hashes" in residual.columns
    assert "product_identity_key" in residual.columns
    assert residual["country"].iloc[0] == "vietnam"


def test_tier_0_propagates_to_sibling_input_hash(fixture_50):
    products, cached = fixture_50
    cache_rows, _, _, _cross_check = cascade(products, cached)
    # 10 tier-0 products × 1 uncached sibling each = 10 new t0 rows
    t0_rows = [r for r in cache_rows if r["match_method"].startswith("input_hash")]
    assert len(t0_rows) == 10
    assert all(r["input_hash"].startswith("t0_new_") for r in t0_rows)


def test_tier_0_does_not_rewrite_already_cached_hashes(fixture_50):
    products, cached = fixture_50
    cache_rows, _, _, _cross_check = cascade(products, cached)
    # The already-cached input_hashes (t0_cached_*) must NOT appear in the new rows.
    written_hashes = {r["input_hash"] for r in cache_rows}
    for i in range(10):
        assert f"t0_cached_{i}" not in written_hashes


def test_tier_1_writes_row_per_input_hash(fixture_50):
    products, cached = fixture_50
    cache_rows, _, _, _cross_check = cascade(products, cached)
    t1_rows = [
        r for r in cache_rows if r["match_method"].startswith("product_identity_key")
    ]
    # 10 tier-1 products × 2 input_hashes each = 20 new rows
    assert len(t1_rows) == 20
    pids = {r["product_identity_key"] for r in t1_rows}
    assert pids == {f"t1_pid_{i}" for i in range(10)}


def test_tier_2_writes_row_per_input_hash(fixture_50):
    products, cached = fixture_50
    cache_rows, _, _, _cross_check = cascade(products, cached)
    t2_rows = [r for r in cache_rows if r["match_method"].startswith("canonical_loose")]
    # 10 tier-2 products × 1 input_hash each = 10 new rows
    assert len(t2_rows) == 10
    # Propagated payload must carry the source coicop_code
    assert all(r["coicop_code"] == "01.2.2" for r in t2_rows)


def test_match_log_includes_country_and_count(fixture_50):
    products, cached = fixture_50
    _, _, log, _cross_check = cascade(products, cached)
    t1 = [r for r in log if r["match_method"].startswith("product_identity_key")]
    assert all(r["country"] == "australia" for r in t1)
    assert all(r["n_input_hashes"] == 2 for r in t1)


def test_empty_cache_pushes_everything_to_residual():
    products = pd.DataFrame(
        [
            _product("pid_a", "loose_a", "philippines", "X", ["h1"]),
            _product("pid_b", "loose_b", "philippines", "Y", ["h2"]),
        ]
    )
    cache_rows, residual, log, _cross_check = cascade(products, pd.DataFrame())
    assert cache_rows == []
    assert log == []
    assert len(residual) == 2


def test_empty_products_returns_empty():
    cached = pd.DataFrame([_cached("h1")])
    cache_rows, residual, log, _cross_check = cascade(
        pd.DataFrame(
            columns=[
                "product_identity_key",
                "canonical_loose",
                "country",
                "first_name",
                "input_hashes",
                "currency",
                "category",
            ]
        ),
        cached,
    )
    assert cache_rows == []
    assert log == []
    assert residual.empty


def test_tier_0_wins_over_tier_1():
    # Same product hits both tier 0 (input_hash) and tier 1 (pid). Tier 0 must win.
    products = pd.DataFrame(
        [_product("pid_x", "loose_x", "philippines", "X", ["h_hit"])]
    )
    cached = pd.DataFrame(
        [
            _cached("h_hit", pid="other_pid", coicop_code="01.0.0"),
            _cached("h_other", pid="pid_x", coicop_code="99.9.9"),
        ]
    )
    cache_rows, residual, log, _cross_check = cascade(products, cached)
    assert len(log) == 1
    assert log[0]["match_method"].startswith("input_hash")
    # No new cache_rows expected: the only input_hash on this product is already cached.
    assert cache_rows == []
    assert residual.empty


def test_tier_1_wins_over_tier_2():
    products = pd.DataFrame(
        [_product("pid_x", "loose_x", "malaysia", "M", ["h_a"], currency="MYR")]
    )
    cached = pd.DataFrame(
        [
            _cached("h_pid", pid="pid_x", country="malaysia", coicop_code="01.0.0"),
            _cached(
                "h_loose",
                pid="other_pid",
                loose="loose_x",
                country="malaysia",
                coicop_code="99.9.9",
            ),
        ]
    )
    cache_rows, _, log, _cross_check = cascade(products, cached)
    assert log[0]["match_method"].startswith("product_identity_key")
    assert all(r["coicop_code"] == "01.0.0" for r in cache_rows)


def test_tier_2_requires_country_match():
    # canonical_loose matches but country differs → no hit.
    products = pd.DataFrame([_product("pid_x", "loose_x", "philippines", "X", ["h1"])])
    cached = pd.DataFrame([_cached("h_other", loose="loose_x", country="malaysia")])
    cache_rows, residual, log, _cross_check = cascade(products, cached)
    assert cache_rows == []
    assert log == []
    assert len(residual) == 1


def test_cache_rows_carry_provenance_columns():
    products = pd.DataFrame(
        [_product("pid_a", "loose_a", "philippines", "X", ["h_new", "h_other"])]
    )
    cached = pd.DataFrame([_cached("h_new")])
    cache_rows, _, _, _cross_check = cascade(products, cached)
    assert len(cache_rows) == 1  # h_other gets propagated, h_new already in cache
    row = cache_rows[0]
    assert row["input_hash"] == "h_other"
    assert row["match_method"].startswith("input_hash")
    assert row["modality"] == "retail"
    assert row["product_identity_key"] == "pid_a"
    assert row["canonical_loose"] == "loose_a"
    assert "schema_version" in row
    assert "created_at" in row


def _sf(**kwargs) -> StructuralFields:
    base = dict(
        pricing_basis=None,
        amount_value=None,
        standard_unit=None,
        count=None,
        multiplier=None,
        is_promotion=None,
        is_bundle=None,
        is_multipack=None,
        promo_reason=None,
    )
    base.update(kwargs)
    return StructuralFields(**base)


def test_overlay_skips_pricing_basis_when_cluster_unanimous():
    payload = {"pricing_basis": "mass", "standard_unit": "kg", "amount_value": 1.0}
    sf = _sf(pricing_basis="volume", standard_unit="lt", amount_value=2.0)
    out = _overlay_tier_a(payload, sf, cluster_agreement_coicop=1.0)
    assert out["pricing_basis"] == "mass"
    assert out["standard_unit"] == "kg"
    assert out["amount_value"] == 2.0  # per-row field always overlays


def test_overlay_applies_pricing_basis_when_cluster_below_threshold():
    payload = {"pricing_basis": "mass", "standard_unit": "kg"}
    sf = _sf(pricing_basis="volume", standard_unit="lt")
    out = _overlay_tier_a(payload, sf, cluster_agreement_coicop=0.7)
    assert out["pricing_basis"] == "volume"
    assert out["standard_unit"] == "lt"


def test_overlay_applies_pricing_basis_when_payload_is_null():
    payload = {"pricing_basis": None, "standard_unit": None}
    sf = _sf(pricing_basis="volume", standard_unit="lt")
    out = _overlay_tier_a(payload, sf, cluster_agreement_coicop=1.0)
    assert out["pricing_basis"] == "volume"
    assert out["standard_unit"] == "lt"


def test_overlay_default_no_cluster_signal_overlays_everything():
    payload = {"pricing_basis": "mass", "standard_unit": "kg"}
    sf = _sf(pricing_basis="volume", standard_unit="lt")
    out = _overlay_tier_a(payload, sf)
    assert out["pricing_basis"] == "volume"
    assert out["standard_unit"] == "lt"


# ─── Phase 6 — tier-b pricing_basis-agreement guard ───────────────────────────


def test_pricing_basis_mismatch_only_when_both_sides_non_null_and_differ():
    assert (
        _pricing_basis_mismatch(_sf(pricing_basis="mass"), {"pricing_basis": "volume"})
        is True
    )
    assert (
        _pricing_basis_mismatch(_sf(pricing_basis="mass"), {"pricing_basis": "mass"})
        is False
    )
    assert (
        _pricing_basis_mismatch(_sf(pricing_basis=None), {"pricing_basis": "volume"})
        is False
    )
    assert (
        _pricing_basis_mismatch(_sf(pricing_basis="mass"), {"pricing_basis": None})
        is False
    )
    assert (
        _pricing_basis_mismatch(_sf(pricing_basis=None), {"pricing_basis": None})
        is False
    )


def test_tier_b_pricing_basis_mismatch_falls_to_residual(monkeypatch):
    """Repro of the Phase 5 Australia almonds→wine bleed:
    cluster is `volume`/`lt` (red wine 750mL), query tier-a extracts `mass` (almonds 750g).
    The guard must reject the tier-b hit so the row falls to tier-c instead of
    inheriting the wine cluster's pricing_basis."""
    from prices.enrich import config
    from prices.enrich.tier_b import index as tier_b_index_mod
    from prices.enrich.stages import enrich as enrich_stage

    miss_rows: list[dict] = []
    monkeypatch.setattr(
        tier_b_index_mod, "append_miss", lambda row: miss_rows.append(row)
    )
    monkeypatch.setattr(
        enrich_stage.tier_b_index, "append_miss", lambda row: miss_rows.append(row)
    )

    def _fake_query(country: str, query_text: str, k=None, channel=None, category=None):
        return tier_b_index_mod.KNNHit(
            accepted=True,
            cluster_id="australia::redwine_750",
            payload={
                "coicop_code": "02.1.1",
                "sub_label_id": "wine",
                "pricing_basis": "volume",
                "standard_unit": "lt",
                "amount_value": 0.75,
            },
            top1_cosine=0.95,
            top1_cluster_agreement=1.0,
            topk_majority=5,
            escalation_reason="hard",
        )

    monkeypatch.setattr(enrich_stage.tier_b_index, "query", _fake_query)
    monkeypatch.setattr(config, "MATCH_TIER_B_ENABLED", True)

    products = pd.DataFrame(
        [
            _product(
                "pid_almonds",
                "loose_almonds",
                "australia",
                "Natural Almonds 750g",
                ["h_almonds"],
                currency="AUD",
                category="snacks",
            )
        ]
    )
    cache_rows, residual, log, _cross_check = cascade(products, pd.DataFrame())

    assert cache_rows == []  # guard fired — no cache row written
    assert log == []
    assert len(residual) == 1
    assert miss_rows and miss_rows[-1]["escalation_reason"] == "pricing_basis_mismatch"
    assert miss_rows[-1]["tier_a_pricing_basis"] == "mass"
    assert miss_rows[-1]["cluster_pricing_basis"] == "volume"


def test_tier_b_pricing_basis_match_accepts_hit(monkeypatch):
    """When tier-a and cluster agree on pricing_basis (both mass), the tier-b
    hit is retained — guard does not fire."""
    from prices.enrich import config
    from prices.enrich.tier_b import index as tier_b_index_mod
    from prices.enrich.stages import enrich as enrich_stage

    def _fake_query(country: str, query_text: str, k=None, channel=None, category=None):
        return tier_b_index_mod.KNNHit(
            accepted=True,
            cluster_id="australia::almonds_750g",
            payload={
                "coicop_code": "01.1.7",
                "sub_label_id": "nuts",
                "pricing_basis": "mass",
                "standard_unit": "kg",
                "amount_value": 0.75,
            },
            top1_cosine=0.95,
            top1_cluster_agreement=1.0,
            topk_majority=5,
            escalation_reason="hard",
        )

    monkeypatch.setattr(enrich_stage.tier_b_index, "query", _fake_query)
    monkeypatch.setattr(config, "MATCH_TIER_B_ENABLED", True)

    products = pd.DataFrame(
        [
            _product(
                "pid_almonds",
                "loose_almonds",
                "australia",
                "Natural Almonds 750g",
                ["h_almonds"],
                currency="AUD",
                category="snacks",
            )
        ]
    )
    cache_rows, residual, log, _cross_check = cascade(products, pd.DataFrame())

    assert len(residual) == 0
    assert len(cache_rows) == 1
    assert cache_rows[0]["match_method"].startswith("tier_b_knn_hard")
    assert cache_rows[0]["pricing_basis"] == "mass"
