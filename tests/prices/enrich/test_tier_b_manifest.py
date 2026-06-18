"""Guard: reindex_all's provenance writers stamp the fat field set.

These tests call the pure meta/manifest builders directly on synthetic inputs
(no data/ read or write) and assert the recorded shape. They prove the writer
emits model_path / git_sha / built_at etc. — closing the provenance gap where a
base index and a fine-tuned index had byte-identical {dim, backend} metadata.
"""

from __future__ import annotations

import pytest

from prices.enrich import config
from prices.enrich.tier_b import index as tier_b_index
from prices.enrich.tier_b import _store

pytestmark = pytest.mark.unit


_FAT_META_FIELDS = {
    "model_path",
    "embed_dim",
    "backend",
    "knn_score_hard_min",
    "n_clusters",
    "built_at",
    "git_sha",
}

_MANIFEST_FIELDS = {
    "countries",
    "model_path",
    "embed_dim",
    "backend",
    "built_at",
    "git_sha",
}


def test_build_meta_carries_fat_provenance_fields():
    meta = tier_b_index.build_meta(n_clusters=42)
    # all seven fat fields present
    assert _FAT_META_FIELDS <= set(
        meta
    ), f"missing fat meta fields: {_FAT_META_FIELDS - set(meta)}"
    # values wired off config (additive — legacy dim/backend preserved too)
    assert meta["model_path"] == config.E5_MODEL_PATH
    assert meta["embed_dim"] == config.EMBED_DIM
    assert meta["backend"] == config.EMBED_BACKEND
    assert meta["n_clusters"] == 42
    assert meta["knn_score_hard_min"] == config.knn_score_hard_min(config.E5_MODEL_PATH)
    # legacy fields the acceptance/_load path still reads — unchanged
    assert meta["dim"] == config.EMBED_DIM


def test_build_meta_built_at_is_utc_iso():
    meta = tier_b_index.build_meta(n_clusters=1)
    # ISO-8601 with an explicit UTC offset (datetime.now(timezone.utc))
    assert meta["built_at"].endswith("+00:00")


def test_build_meta_built_at_override_is_honored():
    meta = tier_b_index.build_meta(n_clusters=1, built_at="2026-01-01T00:00:00+00:00")
    assert meta["built_at"] == "2026-01-01T00:00:00+00:00"


def test_build_manifest_carries_shared_provenance():
    manifest = tier_b_index.build_manifest(["japan", "argentina"])
    assert _MANIFEST_FIELDS <= set(
        manifest
    ), f"missing manifest fields: {_MANIFEST_FIELDS - set(manifest)}"
    # countries sorted, shared provenance stamped
    assert manifest["countries"] == ["argentina", "japan"]
    assert manifest["model_path"] == config.E5_MODEL_PATH
    assert manifest["embed_dim"] == config.EMBED_DIM
    assert manifest["backend"] == config.EMBED_BACKEND


def test_git_sha_is_str_or_none():
    # git_sha is best-effort: a short SHA string in a repo, None if git absent.
    sha = _store._git_sha()
    assert sha is None or isinstance(sha, str)


def test_manifest_path_lives_in_index_dir():
    # additive: manifest.json sits alongside the per-country meta in the index dir.
    assert _store._manifest_path().parent == config.TIER_B_INDEX_DIR
    assert _store._manifest_path().name == "manifest.json"
