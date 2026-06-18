"""Tier-b on-disk index store: build / load / cache the per-country hnswlib
indices, plus the provenance writers (fat per-country meta.json + dir-level
manifest.json).

Split out of index.py to keep that module under the 500-line cap. The
provenance writers are ADDITIVE — acceptance/lookup code reads the same fields
it always read; meta.json / manifest.json only widen what is *recorded* so a
base index and a fine-tuned index are distinguishable from metadata alone.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import hnswlib
import numpy as np
import pandas as pd

from prices.enrich import config
from prices.enrich.tier_b import _anchors
from prices.enrich.tier_b.embed import embed_texts


def _index_path(country: str) -> Path:
    return config.TIER_B_INDEX_DIR / f"{country}.hnsw"


def _clusters_parquet_path(country: str) -> Path:
    return config.TIER_B_INDEX_DIR / f"clusters_{country}.parquet"


def _meta_path(country: str) -> Path:
    return config.TIER_B_INDEX_DIR / f"{country}.meta.json"


def _manifest_path() -> Path:
    return config.TIER_B_INDEX_DIR / "manifest.json"


def _git_sha() -> Optional[str]:
    """Current HEAD short SHA, or None if git is unavailable. Stamped into
    meta/manifest so a base index and a fine-tuned index built from different
    checkouts are distinguishable from metadata alone."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def build_meta(n_clusters: int, built_at: Optional[str] = None) -> dict:
    """Fat per-country provenance record written alongside each index.

    ADDITIVE: the legacy `{dim, backend, n_clusters}` fields are preserved
    (acceptance code reads `dim`/`backend`); the fat fields (model_path,
    embed_dim, knn_score_hard_min, built_at, git_sha) are new and let a base
    index be told apart from a fine-tuned one without reading the folder name.
    """
    if built_at is None:
        built_at = datetime.now(timezone.utc).isoformat()
    return {
        # legacy fields (read by acceptance / _load_index) — unchanged
        "dim": config.EMBED_DIM,
        "backend": config.EMBED_BACKEND,
        "n_clusters": n_clusters,
        # fat provenance (additive)
        "model_path": config.E5_MODEL_PATH,
        "embed_dim": config.EMBED_DIM,
        "knn_score_hard_min": config.knn_score_hard_min(config.E5_MODEL_PATH),
        "built_at": built_at,
        "git_sha": _git_sha(),
    }


def build_manifest(countries: list[str], built_at: Optional[str] = None) -> dict:
    """Dir-level manifest listing the built countries + the shared provenance.

    Written once per reindex_all so the index directory carries its own
    identity (model_path + git_sha + built_at) instead of relying on a
    free-text folder suffix.
    """
    if built_at is None:
        built_at = datetime.now(timezone.utc).isoformat()
    return {
        "countries": sorted(countries),
        "model_path": config.E5_MODEL_PATH,
        "embed_dim": config.EMBED_DIM,
        "backend": config.EMBED_BACKEND,
        "built_at": built_at,
        "git_sha": _git_sha(),
    }


def build_index(cluster_df: pd.DataFrame, country: str) -> Optional[hnswlib.Index]:
    """Build a cosine hnswlib index for one country. Returns None if the
    country falls below KNN_BOOTSTRAP_CLUSTER_FLOOR (real clusters only)."""
    sub = cluster_df[cluster_df["country"] == country].copy()
    if len(sub) < config.KNN_BOOTSTRAP_CLUSTER_FLOOR:
        return None
    anchor_rows = _anchors._make_anchor_rows(country)
    if not anchor_rows.empty:
        sub = pd.concat([sub, anchor_rows], ignore_index=True)
    sub = sub.reset_index(drop=True)
    if "rep_category" not in sub.columns:
        sub["rep_category"] = ""
    sub["rep_category"] = sub["rep_category"].fillna("").astype(str)
    texts = [
        f"passage: {name}" if not cat else f"passage: {cat} | {name}"
        for cat, name in zip(
            sub["rep_category"].tolist(), sub["representative_name"].tolist()
        )
    ]
    vecs = embed_texts(
        texts,
        backend=config.EMBED_BACKEND,
        dim=config.EMBED_DIM,
        use_cache=False,
    )
    idx = hnswlib.Index(space="cosine", dim=config.EMBED_DIM)
    idx.init_index(max_elements=len(sub), ef_construction=200, M=16)
    idx.add_items(vecs, np.arange(len(sub)))
    idx.set_ef(64)

    config.TIER_B_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    idx.save_index(str(_index_path(country)))
    sub.to_parquet(_clusters_parquet_path(country), index=False)
    n_real = int((sub["channel"] != "_anchor").sum())
    _meta_path(country).write_text(json.dumps(build_meta(n_real)))
    return idx


def _load_index(country: str) -> Optional[tuple[hnswlib.Index, pd.DataFrame]]:
    ip = _index_path(country)
    cp = _clusters_parquet_path(country)
    if not ip.exists() or not cp.exists():
        return None
    idx = hnswlib.Index(space="cosine", dim=config.EMBED_DIM)
    idx.load_index(str(ip))
    idx.set_ef(64)
    clusters = pd.read_parquet(cp)
    return idx, clusters


_INDEX_CACHE: dict[str, Optional[tuple[hnswlib.Index, pd.DataFrame]]] = {}


def _get_index(country: str) -> Optional[tuple[hnswlib.Index, pd.DataFrame]]:
    if country not in _INDEX_CACHE:
        _INDEX_CACHE[country] = _load_index(country)
    return _INDEX_CACHE[country]


def reset_index_cache() -> None:
    _INDEX_CACHE.clear()
