"""Tier (b) — cluster-resolved KNN over the enrichments cache (public facade).

Two-stage:
    1. cluster_cache(cache_df) — group cache rows by canonical product
       identity, resolve a single label per cluster via majority vote per
       field, choose a representative item name (longest-string tiebreak).
    2. build_index(cluster_df, country) — embed cluster reps with `passage:`
       prefix, build a per-country hnswlib cosine index. query() embeds the
       lookup with `query:` prefix and applies two-tier accept thresholds
       (hard τ_high + cluster_agreement, soft top-K majority + τ_low).

`reindex_all()` is a synchronous full rebuild; it writes one .hnsw per country
plus a `clusters_<country>.parquet`, a fat per-country `meta.json`, and one
dir-level `manifest.json`. Bootstrap floor skips countries with too few
clusters to bother.

The tier-b layer is split across this package for the 500-line cap:
`_anchors` (COICOP anchor/exclude data), `_cluster` (cluster_cache + KNNHit),
`_store` (build/load/cache + meta/manifest writers), `_lookup` (pick/accept/
query). This module re-exports the public surface so every existing call site
(`from prices.enrich.tier_b import index as tier_b_index`, then
`tier_b_index.query / .cluster_cache / .KNNHit / .append_miss / ...`) keeps
resolving unchanged.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from prices.enrich import config

# Re-exported public surface — keep these importable from this module so the
# `tier_b_index.<symbol>` call pattern (and the eval harness's `append_miss`
# monkeypatch on this module object) resolves exactly as before the split.
from prices.enrich.tier_b._anchors import _make_anchor_rows  # noqa: F401
from prices.enrich.tier_b._cluster import KNNHit, cluster_cache  # noqa: F401
from prices.enrich.tier_b._lookup import (  # noqa: F401
    accept_from_picked,
    pick_neighbors,
    query,
)
from prices.enrich.tier_b._store import (  # noqa: F401
    _get_index,
    _load_index,
    build_index,
    build_manifest,
    build_meta,
    reset_index_cache,
)
from prices.enrich.tier_b._store import _manifest_path


def reindex_all(cache_df: Optional[pd.DataFrame] = None) -> dict[str, int]:
    """Cluster, then build one index per country. Returns {country: n_clusters}
    for indices actually built (skipped countries omitted)."""
    if cache_df is None:
        from prices.enrich.tier_b import cache as cache_mod

        cache_df = cache_mod.read_cache()
    if cache_df.empty:
        return {}
    clusters = cluster_cache(cache_df)
    if clusters.empty:
        return {}
    built: dict[str, int] = {}
    for country in sorted(clusters["country"].unique()):
        idx = build_index(clusters, country)
        if idx is not None:
            built[country] = int((clusters["country"] == country).sum())
    if built:
        import json

        config.TIER_B_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _manifest_path().write_text(json.dumps(build_manifest(list(built.keys()))))
    reset_index_cache()
    return built


def append_miss(row: dict) -> None:
    """Append a tier-b reject row to the misses parquet (telemetry)."""
    p = config.TIER_B_MISSES_PARQUET
    p.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame([row])
    if p.exists():
        out = pd.concat([pd.read_parquet(p), new], ignore_index=True)
    else:
        out = new
    out.to_parquet(p, index=False)
