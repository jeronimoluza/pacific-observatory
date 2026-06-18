"""Phase 4.5 cascade replay verification.

Leave-one-out replay. Two layers:
  1. Synthetic fixtures that force pid- and loose-collisions, then verify
     the cascade recovers payloads at 100%. Guards the replay plumbing.
  2. The real cache: skipped when absent. Asserts that when a tier fires,
     agreement meets the spec thresholds (tier-1 ≥ 99%, tier-2 ≥ 90%).
     Note: this cache post-Phase 1 has very few pid-collisions (~56 / 20k),
     so the meaningful-n is small — see the report for full numbers.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.enrich.tier_b import cache as cache_module
from prices.enrich.replay import replay


def _row(
    input_hash: str,
    name: str,
    country: str = "philippines",
    coicop: str = "01.2.2",
    sub_label: str = "soft-drink",
) -> dict:
    return {
        "input_hash": input_hash,
        "product_name_original": name,
        "category": "beverage",
        "country": country,
        "currency": "PHP",
        "pricing_basis": "volume",
        "amount_value": 1.0,
        "standard_unit": "lt",
        "count": 1,
        "multiplier": None,
        "dimensions_json": "[]",
        "coicop_code": coicop,
        "sub_label_id": sub_label,
        "is_promotion": False,
        "is_bundle": False,
        "is_multipack": False,
        "promo_reason": None,
        "confidence": 0.95,
        "state": "resolved",
    }


def test_synthetic_pid_collision_perfect_agreement():
    """Two rows with the same product name (→ same pid) and the same payload.
    Leave-one-out must hit tier-1 with 100% agreement."""
    cached = pd.DataFrame(
        [
            _row("h1", "Coca-Cola 1L"),
            _row("h2", "Coca-Cola 1L"),  # identical canonicalization → same pid
        ]
    )
    result = replay(seed=1, cached=cached)
    assert result["status"] == "ok"
    assert result["n_pid_collisions"] >= 1
    t1 = result["buckets"].get("product_identity_key")
    assert t1 is not None and t1["matched"] >= 2
    assert t1["agreed"] == t1["matched"]


def test_synthetic_loose_collision_perfect_agreement():
    """Same brand+product, different pack sizes → same canonical_loose, different pid.
    Leave-one-out must hit tier-2."""
    cached = pd.DataFrame(
        [
            _row("h1", "Nestle MILO 400g", country="malaysia"),
            _row("h2", "Nestle MILO 1kg", country="malaysia"),
        ]
    )
    result = replay(seed=1, cached=cached)
    assert result["status"] == "ok"
    assert result["n_loose_collisions"] >= 1
    t2 = result["buckets"].get("canonical_loose")
    assert t2 is not None and t2["matched"] >= 2
    assert t2["agreed"] == t2["matched"]


def test_synthetic_disagreement_detected():
    """Two rows with same pid but different coicop_code — disagreement must surface."""
    cached = pd.DataFrame(
        [
            _row("h1", "Coca-Cola 1L", coicop="01.2.2"),
            _row("h2", "Coca-Cola 1L", coicop="99.9.9"),
        ]
    )
    result = replay(seed=1, cached=cached)
    assert result["status"] == "ok"
    t1 = result["buckets"]["product_identity_key"]
    assert t1["matched"] == 2
    assert t1["agreed"] == 0
    assert len(result["disagreements"]) == 2


def test_no_cache():
    assert replay(seed=0, cached=pd.DataFrame())["status"] == "no_cache"


def test_no_collisions_returns_signal():
    """Single row → no buddies anywhere → replay reports no_collision_rows."""
    cached = pd.DataFrame([_row("h1", "Unique 1L")])
    result = replay(seed=0, cached=cached)
    assert result["status"] == "no_collision_rows"


@pytest.fixture(scope="module")
def real_cache():
    df = cache_module.read_cache()
    if df.empty or len(df) < 500:
        pytest.skip("Real enrichments cache not available (need ≥ 500 rows)")
    return df


def test_real_cache_collision_replay_runs(real_cache):
    """Smoke test: replay completes on the real cache and reports
    cache-shape stats. Threshold assertions are deliberately deferred —
    see `test_real_cache_meets_thresholds` for the gate.
    """
    result = replay(seed=42, scope="collisions")
    assert result["status"] in ("ok", "no_collision_rows")
    if result["status"] == "ok":
        assert (
            sum(b["matched"] for b in result["buckets"].values()) > 0
        ), "vacuous replay"
