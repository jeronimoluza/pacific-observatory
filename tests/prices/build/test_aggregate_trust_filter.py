from __future__ import annotations

import pandas as pd
import pytest

from prices.build import aggregate

pytestmark = pytest.mark.unit


def _fake_classified_rows() -> pd.DataFrame:
    """A classified.parquet-shaped frame (one row per input_hash).

    Covers the two live "keep" states (narrow_source / classified) across every
    trust_level, plus a `rejected` row that the state filter must drop.
    """
    base = {
        "coicop_code": "01.1.1.0.0",
        "state": "classified",
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
        {**base, "input_hash": "h_high", "trust_level": "high"},
        {**base, "input_hash": "h_low", "trust_level": "low"},
        {**base, "input_hash": "h_flagged", "trust_level": "flagged"},
        {**base, "input_hash": "h_missing", "trust_level": None},
        {**base, "input_hash": "h_rejected", "state": "rejected",
         "trust_level": "low"},
    ]
    return pd.DataFrame(rows)


def _patch_classified(tmp_path, monkeypatch) -> None:
    path = tmp_path / "classified.parquet"
    _fake_classified_rows().to_parquet(path)
    # BUILD_CLASSIFIED_PARQUET, not CLASSIFIED_PARQUET: build reads whichever
    # file the ACTIVE backend wrote, and under hierlex that is
    # classified_hierlex.parquet. Patching the head's constant left the real one
    # pointing at a file that does not exist on a hierlex box.
    monkeypatch.setattr(aggregate.enrich_config, "BUILD_CLASSIFIED_PARQUET", path)
    monkeypatch.setattr(aggregate, "FNB_COICOP_PREFIXES", ("01.",))


def test_load_filtered_cache_excludes_non_high_trust(tmp_path, monkeypatch):
    _patch_classified(tmp_path, monkeypatch)

    out = aggregate.load_filtered_cache()

    # low/flagged dropped by the trust filter; rejected dropped by the state
    # filter; None trust_level defaults to high and is kept.
    assert set(out["input_hash"]) == {"h_high", "h_missing"}
    assert set(out["trust_level"]) == {"high"}


def test_compute_unit_values_never_sees_non_high_trust(tmp_path, monkeypatch):
    _patch_classified(tmp_path, monkeypatch)

    cache = aggregate.load_filtered_cache()
    # In the real pipeline `price`/`currency` arrive from the
    # products_input/raw-CSV side of the join (not in CACHE_KEEP_COLS) — attach
    # them here to simulate the post-join frame _compute_unit_values expects.
    cache = cache.assign(price=10.0, currency="USD")
    result = aggregate._compute_unit_values(cache)

    assert set(result["input_hash"]) == {"h_high", "h_missing"}
    assert result["unit_value_local"].notna().all()
