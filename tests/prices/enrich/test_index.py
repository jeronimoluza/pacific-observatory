"""Tier (b) index — synthetic-cosine tests that bypass the real embedding
backend by monkeypatching `embed_texts` to a deterministic 1-hot/cosine
generator. Real-embedding behavior is covered by test_embed.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.enrich import config
from prices.enrich.tier_b import _lookup as _tier_b_lookup
from prices.enrich.tier_b import _store as _tier_b_store
from prices.enrich.tier_b import index as tier_b_index


def _patch_embed(monkeypatch, fn):
    """embed_texts is referenced from both the build path (_store) and the
    query path (_lookup) after the tier_b package split; patch both so the
    synthetic-cosine generator covers build + lookup."""
    monkeypatch.setattr(_tier_b_store, "embed_texts", fn)
    monkeypatch.setattr(_tier_b_lookup, "embed_texts", fn)


@pytest.fixture(autouse=True)
def _reset_index_cache():
    tier_b_index.reset_index_cache()
    yield
    tier_b_index.reset_index_cache()


@pytest.fixture
def low_floor(monkeypatch):
    """Lower the bootstrap floor to allow small synthetic fixtures."""
    monkeypatch.setattr(config, "KNN_BOOTSTRAP_CLUSTER_FLOOR", 3)
    return None


def _make_cache_df(rows: list[dict]) -> pd.DataFrame:
    base = {
        "product_name_original": "",
        "country": "",
        "coicop_code": "",
        "sub_label_id": "",
        "state": "ok",
        "pricing_basis": "item",
        "standard_unit": "unit",
        "amount_value": None,
        "count": None,
        "multiplier": None,
        "is_promotion": False,
        "is_bundle": False,
        "is_multipack": False,
        "promo_reason": None,
        "confidence": 0.9,
    }
    df = pd.DataFrame([{**base, **r} for r in rows])
    return df


def test_cluster_majority_resolves_per_field():
    rows = [
        {
            "product_name_original": "Coca Cola 330ml",
            "country": "mexico",
            "coicop_code": "01.2.1",
            "sub_label_id": "soda_330ml",
        }
    ] * 4 + [
        {
            "product_name_original": "Coca Cola 330ml",
            "country": "mexico",
            "coicop_code": "WRONG",
            "sub_label_id": "WRONG",
        }
    ]
    cache = _make_cache_df(rows)
    clusters = tier_b_index.cluster_cache(cache)
    assert len(clusters) == 1
    row = clusters.iloc[0]
    assert row["coicop_code"] == "01.2.1"
    assert row["sub_label_id"] == "soda_330ml"
    assert row["cluster_size"] == 5
    assert row["cluster_agreement_coicop"] == pytest.approx(0.8)


def test_country_partitions_separately():
    cache = _make_cache_df(
        [
            {
                "product_name_original": "Pan integral",
                "country": "mexico",
                "coicop_code": "01.1.1",
            },
            {
                "product_name_original": "Pan integral",
                "country": "argentina",
                "coicop_code": "01.1.1",
            },
        ]
    )
    clusters = tier_b_index.cluster_cache(cache)
    assert set(clusters["country"]) == {"mexico", "argentina"}
    assert len(clusters) == 2


def _patch_embed_orthonormal(monkeypatch, mapping: dict[str, int], dim: int = 32):
    """Map each input string to a unit vector; aligned strings → cosine=1.0,
    different keys → cosine=0.0 unless they share an index. Unknown keys map
    to a sentinel slot (dim-1) reserved by the test caller."""
    sentinel = dim - 1

    def _embed(texts, backend=None, dim=dim, use_cache=False):
        out = np.zeros((len(texts), dim), dtype=np.float32)
        for i, t in enumerate(texts):
            key = t.split(": ", 1)[-1]
            slot = mapping.get(key, sentinel)
            out[i, slot] = 1.0
        return out

    _patch_embed(monkeypatch, _embed)
    monkeypatch.setattr(config, "EMBED_DIM", dim)


def test_hard_accept_threshold(monkeypatch, tmp_path, low_floor):
    monkeypatch.setattr(config, "TIER_B_INDEX_DIR", tmp_path)
    mapping = {f"prod_{i}": i for i in range(10)}
    _patch_embed_orthonormal(monkeypatch, mapping)

    # 10 distinct cluster reps; each cluster has 10 rows w/ unanimous coicop.
    rows = []
    for i in range(10):
        for _ in range(10):
            rows.append(
                {
                    "product_name_original": f"prod_{i}",
                    "country": "x",
                    "coicop_code": f"C{i}",
                    "sub_label_id": f"S{i}",
                }
            )
    cache = _make_cache_df(rows)
    clusters = tier_b_index.cluster_cache(cache)
    tier_b_index.build_index(clusters, "x")

    # Identical query string → cosine 1.0, unanimous cluster → accept.
    tier_b_index.reset_index_cache()
    hit = tier_b_index.query("x", "prod_3")
    assert hit.accepted is True
    assert hit.escalation_reason == "hard"
    assert hit.payload["coicop_code"] == "C3"


def test_soft_accept_with_majority(monkeypatch, tmp_path, low_floor):
    """Top-1 cosine below τ_high but above τ_low, and 3+/5 neighbors share coicop."""
    monkeypatch.setattr(config, "TIER_B_INDEX_DIR", tmp_path)
    monkeypatch.setitem(config.KNN_SCORE_HARD_MIN, config.E5_MODEL_PATH, 0.99)
    monkeypatch.setattr(config, "KNN_TAU_LOW", 0.50)
    dim = 4
    # Vectors hand-crafted so the query is closest to one cluster (cosine ~0.7) and
    # 3 of the top-5 carry the same coicop.
    vec_db = np.array(
        [
            [1, 1, 0, 0],
            [1, 0, 1, 0],
            [1, 0, 0, 1],
            [0, 1, 1, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float32,
    )
    vec_db = vec_db / np.linalg.norm(vec_db, axis=1, keepdims=True)
    vec_q = np.array([[1, 1, 1, 0]], dtype=np.float32)
    vec_q = vec_q / np.linalg.norm(vec_q)

    text_to_vec: dict[str, np.ndarray] = {f"rep_{i}": vec_db[i] for i in range(5)}
    text_to_vec["query_x"] = vec_q[0]

    def _embed(texts, backend=None, dim=dim, use_cache=False):
        return np.array(
            [text_to_vec[t.split(": ", 1)[-1]] for t in texts], dtype=np.float32
        )

    _patch_embed(monkeypatch, _embed)
    monkeypatch.setattr(config, "EMBED_DIM", dim)

    rows = []
    for i in range(5):
        coicop = "MAJORITY" if i in (0, 1, 2) else f"MINOR_{i}"
        for _ in range(3):
            rows.append(
                {
                    "product_name_original": f"rep_{i}",
                    "country": "x",
                    "coicop_code": coicop,
                    "sub_label_id": f"S{i}",
                }
            )
    cache = _make_cache_df(rows)
    clusters = tier_b_index.cluster_cache(cache)
    tier_b_index.build_index(clusters, "x")
    tier_b_index.reset_index_cache()

    hit = tier_b_index.query("x", "query_x")
    assert hit.accepted is True
    assert hit.escalation_reason == "soft"
    assert hit.payload["coicop_code"] == "MAJORITY"
    assert hit.topk_majority >= 3


def test_miss_below_thresholds(monkeypatch, tmp_path, low_floor):
    monkeypatch.setattr(config, "TIER_B_INDEX_DIR", tmp_path)
    monkeypatch.setitem(config.KNN_SCORE_HARD_MIN, config.E5_MODEL_PATH, 0.99)
    monkeypatch.setattr(config, "KNN_TAU_LOW", 0.99)  # impossible
    mapping = {f"prod_{i}": i for i in range(5)}
    _patch_embed_orthonormal(monkeypatch, mapping)

    rows = []
    for i in range(5):
        for _ in range(3):
            rows.append(
                {
                    "product_name_original": f"prod_{i}",
                    "country": "x",
                    "coicop_code": f"C{i}",
                    "sub_label_id": f"S{i}",
                }
            )
    cache = _make_cache_df(rows)
    clusters = tier_b_index.cluster_cache(cache)
    tier_b_index.build_index(clusters, "x")
    tier_b_index.reset_index_cache()

    # Query string not in mapping → cosine 0 vs every cluster rep → reject.
    hit = tier_b_index.query("x", "totally_unknown")
    assert hit.accepted is False
    assert hit.escalation_reason == "miss"


def test_bootstrap_floor_skips_small_country(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "TIER_B_INDEX_DIR", tmp_path)
    monkeypatch.setattr(config, "KNN_BOOTSTRAP_CLUSTER_FLOOR", 100)
    mapping = {f"prod_{i}": i for i in range(5)}
    _patch_embed_orthonormal(monkeypatch, mapping)

    rows = [
        {
            "product_name_original": f"prod_{i}",
            "country": "tiny",
            "coicop_code": f"C{i}",
            "sub_label_id": f"S{i}",
        }
        for i in range(5)
    ]
    cache = _make_cache_df(rows)
    clusters = tier_b_index.cluster_cache(cache)
    idx = tier_b_index.build_index(clusters, "tiny")
    assert idx is None

    # Even if query is invoked, return skip_bootstrap since no index was built.
    tier_b_index.reset_index_cache()
    hit = tier_b_index.query("tiny", "prod_1")
    assert hit.accepted is False
    assert hit.escalation_reason == "no_index"


def test_query_country_isolation(monkeypatch, tmp_path, low_floor):
    monkeypatch.setattr(config, "TIER_B_INDEX_DIR", tmp_path)
    # Two countries; only build the index for "a". Queries for "b" → no_index.
    mapping = {f"prod_{i}": i for i in range(5)}
    _patch_embed_orthonormal(monkeypatch, mapping)
    rows = [
        {
            "product_name_original": f"prod_{i}",
            "country": "a",
            "coicop_code": f"C{i}",
            "sub_label_id": f"S{i}",
        }
        for i in range(5)
        for _ in range(3)
    ]
    cache = _make_cache_df(rows)
    clusters = tier_b_index.cluster_cache(cache)
    tier_b_index.build_index(clusters, "a")
    tier_b_index.reset_index_cache()

    assert tier_b_index.query("b", "prod_1").escalation_reason == "no_index"
    assert tier_b_index.query("a", "prod_1").accepted is True
