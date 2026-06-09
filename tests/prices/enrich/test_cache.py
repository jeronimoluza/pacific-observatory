import pandas as pd
import pytest

from prices.enrich import cache, config


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "ENRICHMENTS_PARQUET", tmp_path / "enrichments.parquet")
    monkeypatch.setattr(config, "FAILED_PARQUET", tmp_path / "_failed.parquet")
    yield


def _enrichment_row(cache_key="abc", input_hash="h1", state="resolved"):
    return {
        "cache_key": cache_key,
        "input_hash": input_hash,
        "pricing_basis": "mass",
        "amount_value": 1.0,
        "standard_unit": "kg",
        "count": None,
        "multiplier": None,
        "coicop_code": "01.1.1.3",
        "sub_label_id": "_other",
        "is_promotion": False,
        "is_bundle": False,
        "is_multipack": False,
        "promo_reason": None,
        "confidence": 0.9,
        "state": state,
        "raw_response_text": "{}",
        "total_tokens": 42,
        "model_version": "gemini-3.1-flash-lite",
        "prompt_semver": "v1",
        "prompt_bytes_hash": "p",
        "schema_version": "s",
        "taxonomy_version": "t",
        "trust_level": "high",
        "created_at": "2026-05-27T00:00:00+00:00",
    }


def _failure_row(cache_key="dup", input_hash="h"):
    return {
        "cache_key": cache_key,
        "input_hash": input_hash,
        "product_name_original": "Coke 1L",
        "category": "Drinks",
        "country": "PH",
        "currency": "PHP",
        "last_error": "504 timeout",
        "attempt_count": 3,
        "failed_at": "2026-05-27T00:00:00+00:00",
    }


def test_read_cache_empty_when_no_file():
    out = cache.read_cache()
    assert isinstance(out, pd.DataFrame)
    assert out.empty


def test_existing_keys_empty_when_no_file():
    assert cache.existing_keys() == set()


def test_append_then_read_roundtrip():
    cache.append_enrichments([_enrichment_row("abc", "h1")])
    out = cache.read_cache()
    assert len(out) == 1
    assert out.iloc[0]["cache_key"] == "abc"
    assert out.iloc[0]["sub_label_id"] == "_other"


def test_append_enrichments_appends_not_overwrites():
    cache.append_enrichments([_enrichment_row("k1", "h1")])
    cache.append_enrichments([_enrichment_row("k2", "h2")])
    out = cache.read_cache()
    assert len(out) == 2
    assert set(out["cache_key"]) == {"k1", "k2"}


def test_existing_keys_returns_set():
    cache.append_enrichments([_enrichment_row("k1", "h1")])
    assert cache.existing_keys() == {"k1"}


def test_append_failures_creates_parquet():
    cache.append_failures([_failure_row("f1", "h_f1")])
    df = pd.read_parquet(config.FAILED_PARQUET)
    assert len(df) == 1
    assert df.iloc[0]["last_error"] == "504 timeout"


def test_enforce_collision_invariant_prunes_overlap():
    cache.append_enrichments([_enrichment_row("dup", "h")])
    cache.append_failures([_failure_row("dup", "h")])
    pruned = cache.enforce_collision_invariant()
    assert pruned == 1
    after = pd.read_parquet(config.FAILED_PARQUET)
    assert after.empty


def test_enforce_collision_invariant_no_op_when_no_overlap():
    cache.append_enrichments([_enrichment_row("k1", "h1")])
    cache.append_failures([_failure_row("k2", "h2")])
    pruned = cache.enforce_collision_invariant()
    assert pruned == 0
    after = pd.read_parquet(config.FAILED_PARQUET)
    assert len(after) == 1


def test_enforce_collision_invariant_no_op_when_files_missing():
    assert cache.enforce_collision_invariant() == 0


def test_append_empty_list_is_noop():
    cache.append_enrichments([])
    assert cache.read_cache().empty
    cache.append_failures([])
    assert not config.FAILED_PARQUET.exists()
