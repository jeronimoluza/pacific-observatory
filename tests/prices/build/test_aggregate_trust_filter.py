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


def test_cache_is_one_row_per_hash_even_when_parts_repeat_a_name(tmp_path, monkeypatch):
    """The decisions table is a directory of per-country parts keyed by a hash of
    the NAME, so an aggregator name sold in many countries is written once per
    part. The join is on input_hash alone, so every extra copy fans a
    products_input row out into an extra snapshot row -- measured at 11,964
    duplicated snapshot rows before this dedupe."""
    rows = _fake_classified_rows()
    path = tmp_path / "classified.parquet"
    pd.concat([rows, rows, rows], ignore_index=True).to_parquet(path)
    monkeypatch.setattr(aggregate.enrich_config, "BUILD_CLASSIFIED_PARQUET", path)
    monkeypatch.setattr(aggregate, "FNB_COICOP_PREFIXES", ("01.",))

    out = aggregate.load_filtered_cache()

    assert not out["input_hash"].duplicated().any()
    assert set(out["input_hash"]) == {"h_high", "h_missing"}


def test_a_hash_with_two_different_classifications_is_not_silently_collapsed(
    tmp_path, monkeypatch
):
    """Dedupe is on the whole row, not the key. Identical copies are an artifact
    of per-country parts and drop harmlessly; two genuinely DIFFERENT rulings for
    one hash are a real disagreement, and must survive to be caught downstream
    rather than be resolved by whichever row happened to sort first."""
    rows = _fake_classified_rows()
    conflicting = rows[rows["input_hash"] == "h_high"].copy()
    conflicting["coicop_code"] = "01.1.2.0.0"
    path = tmp_path / "classified.parquet"
    pd.concat([rows, conflicting], ignore_index=True).to_parquet(path)
    monkeypatch.setattr(aggregate.enrich_config, "BUILD_CLASSIFIED_PARQUET", path)
    monkeypatch.setattr(aggregate, "FNB_COICOP_PREFIXES", ("01.",))

    out = aggregate.load_filtered_cache()

    assert (out["input_hash"] == "h_high").sum() == 2
    assert set(out.loc[out["input_hash"] == "h_high", "coicop_code"]) == {
        "01.1.1.0.0",
        "01.1.2.0.0",
    }
