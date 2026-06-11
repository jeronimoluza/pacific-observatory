"""Tier (b) — cluster-resolved KNN over the enrichments cache.

Two-stage:
    1. cluster_cache(cache_df) — group cache rows by canonical product
       identity, resolve a single label per cluster via majority vote per
       field, choose a representative item name (longest-string tiebreak).
    2. build_index(cluster_df, country) — embed cluster reps with `passage:`
       prefix, build a per-country hnswlib cosine index. query() embeds the
       lookup with `query:` prefix and applies two-tier accept thresholds
       (hard τ_high + cluster_agreement, soft top-K majority + τ_low).

`reindex_all()` is a synchronous full rebuild; it writes one .hnsw per country
plus a `clusters_<country>.parquet`. Bootstrap floor skips countries with too
few clusters to bother.

Schema does not require pid/canonical_loose columns in the cache — we compute
canonical_strict on the fly from product_name_original + country.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import hnswlib
import numpy as np
import pandas as pd

from prices.enrich import config
from prices.enrich.embed import embed_texts
from prices.enrich.normalize import (
    canonicalize,
    normalize_breadcrumb,
    resolve_cluster_category,
)


_CLUSTER_LABEL_FIELDS = (
    "coicop_code",
    "sub_label_id",
    "state",
)


@dataclass(frozen=True)
class KNNHit:
    accepted: bool
    cluster_id: str
    payload: dict
    top1_cosine: float
    top1_cluster_agreement: float
    topk_majority: int
    escalation_reason: str  # "hard", "soft", "miss", "skip_bootstrap", "no_index"


def _resolve_lang(country: str) -> Optional[str]:
    try:
        from core.config import load_countries

        meta = load_countries().get(country) or {}
        langs = meta.get("languages") or []
        return langs[0] if langs else None
    except Exception:
        return None


def _majority(values: list) -> tuple[Optional[object], int, int]:
    """Return (top_value, top_count, total_non_null). None if all null."""
    vs = [
        v
        for v in values
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    ]
    if not vs:
        return None, 0, 0
    c = Counter(vs)
    val, cnt = c.most_common(1)[0]
    return val, cnt, len(vs)


def _pick_rep(names: list[str]) -> str:
    """Most-common, longest-string tiebreak."""
    if not names:
        return ""
    c = Counter(names)
    top = c.most_common()
    top_count = top[0][1]
    candidates = [n for n, k in top if k == top_count]
    return max(candidates, key=len)


def cluster_cache(cache_df: pd.DataFrame) -> pd.DataFrame:
    """Group cache rows by (canonical_strict, country, channel) — produce one
    cluster per identity with majority-resolved labels and a representative
    name. Legacy rows without channel partition as channel=``"null"``."""
    if cache_df.empty:
        return pd.DataFrame()
    df = cache_df.copy()
    df["country"] = df["country"].fillna("").astype(str)
    if "channel" not in df.columns:
        df["channel"] = "null"
    else:
        df["channel"] = df["channel"].fillna("null").astype(str)
        df.loc[df["channel"] == "", "channel"] = "null"
    if "canonical_strict" in df.columns:
        df["__strict__"] = df["canonical_strict"].fillna("")
    else:
        lang_cache: dict[str, Optional[str]] = {}

        def _strict(row) -> str:
            country = row["country"]
            if country not in lang_cache:
                lang_cache[country] = _resolve_lang(country)
            canon = canonicalize(
                item_name=str(row.get("product_name_original") or ""),
                category=str(row.get("category") or "") or None,
                country=country,
                lang=lang_cache[country],
            )
            return canon.canonical_strict or ""

        df["__strict__"] = df.apply(_strict, axis=1)

    df = df[df["__strict__"].astype(str).str.len() > 0]
    if df.empty:
        return pd.DataFrame()

    has_category = "category" in df.columns
    out_rows: list[dict] = []
    for (strict, country, channel), grp in df.groupby(
        ["__strict__", "country", "channel"]
    ):
        names = grp["product_name_original"].astype(str).tolist()
        rep = _pick_rep(names)
        if has_category:
            rep_category = resolve_cluster_category(grp["category"].tolist())
        else:
            rep_category = ""
        resolved: dict = {}
        agreements: dict = {}
        for f in _CLUSTER_LABEL_FIELDS:
            vals = grp[f].tolist() if f in grp.columns else []
            top, cnt, total = _majority(vals)
            resolved[f] = top
            agreements[f] = (cnt / total) if total else 0.0
        for f in (
            "pricing_basis",
            "standard_unit",
            "amount_value",
            "count",
            "multiplier",
            "is_promotion",
            "is_bundle",
            "is_multipack",
            "promo_reason",
            "confidence",
        ):
            if f in grp.columns:
                vals = grp[f].tolist()
                top, _, _ = _majority(vals)
                resolved[f] = top

        cluster_id = f"{country}::{channel}::{strict}"
        out_rows.append(
            {
                "cluster_id": cluster_id,
                "country": country,
                "channel": channel,
                "canonical_strict": strict,
                "representative_name": rep,
                "rep_category": rep_category,
                "cluster_size": int(len(grp)),
                "cluster_agreement_coicop": float(agreements.get("coicop_code", 0.0)),
                "cluster_agreement_sub_label": float(
                    agreements.get("sub_label_id", 0.0)
                ),
                **resolved,
            }
        )
    return pd.DataFrame(out_rows)


def _index_path(country: str) -> Path:
    return config.TIER_B_INDEX_DIR / f"{country}.hnsw"


def _clusters_parquet_path(country: str) -> Path:
    return config.TIER_B_INDEX_DIR / f"clusters_{country}.parquet"


def _meta_path(country: str) -> Path:
    return config.TIER_B_INDEX_DIR / f"{country}.meta.json"


def build_index(cluster_df: pd.DataFrame, country: str) -> Optional[hnswlib.Index]:
    """Build a cosine hnswlib index for one country. Returns None if the
    country falls below KNN_BOOTSTRAP_CLUSTER_FLOOR."""
    sub = cluster_df[cluster_df["country"] == country].copy()
    if len(sub) < config.KNN_BOOTSTRAP_CLUSTER_FLOOR:
        return None
    sub = sub.reset_index(drop=True)
    if "rep_category" not in sub.columns:
        sub["rep_category"] = ""
    sub["rep_category"] = sub["rep_category"].fillna("").astype(str)
    texts = [
        f"passage: {cat} | {name}" if cat else f"passage: {name}"
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
    _meta_path(country).write_text(
        json.dumps(
            {
                "dim": config.EMBED_DIM,
                "backend": config.EMBED_BACKEND,
                "n_clusters": int(len(sub)),
            }
        )
    )
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


def pick_neighbors(
    country: str,
    query_text: str,
    k: Optional[int] = None,
    channel: Optional[str] = None,
    category: Optional[str] = None,
) -> tuple[Optional[list[tuple[int, float]]], bool, Optional[pd.DataFrame], str]:
    """Stage 1: run the HNSW lookup and same-channel filter; return the picked
    neighbor list, cross_channel_accept flag, and the loaded cluster table.
    Stops before the accept logic so callers can apply additional filtering
    (see pool_filter.apply_hard_drop / apply_rank_boost).

    Returns (picked, cross_channel_accept, clusters, escalation_reason). When
    picked is None, escalation_reason is one of: 'no_index', 'skip_bootstrap',
    'miss'. The bake-off harness uses this entry point; production `query()`
    wraps it with the standard accept logic below.
    """
    k = k or config.KNN_K
    loaded = _get_index(country)
    if loaded is None:
        return None, False, None, "no_index"
    idx, clusters = loaded
    if len(clusters) < config.KNN_BOOTSTRAP_CLUSTER_FLOOR:
        return None, False, clusters, "skip_bootstrap"

    overfetch = max(k, k * getattr(config, "KNN_CHANNEL_OVERFETCH", 4))
    k_eff = min(overfetch, len(clusters))
    norm_category = normalize_breadcrumb(category) if category else ""
    query_str = (
        f"query: {norm_category} | {query_text}"
        if norm_category
        else f"query: {query_text}"
    )
    vec = embed_texts([query_str], backend=config.EMBED_BACKEND, dim=config.EMBED_DIM)
    raw_labels, raw_dists = idx.knn_query(vec, k=k_eff)
    raw_labels = list(raw_labels[0])
    raw_cosines = list(1.0 - raw_dists[0])

    cross_channel_accept = False
    if channel and "channel" in clusters.columns:
        same: list[tuple[int, float]] = []
        other: list[tuple[int, float]] = []
        for lab, cos in zip(raw_labels, raw_cosines):
            row_channel = clusters.iloc[int(lab)].get("channel") or "null"
            if str(row_channel) == channel:
                same.append((int(lab), float(cos)))
            else:
                other.append((int(lab), float(cos)))
        min_same = getattr(config, "MIN_SAME_CHANNEL_KNN", 3)
        if len(same) >= min_same:
            picked = same[:k]
        else:
            cross_channel_accept = True
            picked = (same + other)[:k]
    else:
        picked = list(
            zip([int(lab) for lab in raw_labels], [float(c) for c in raw_cosines])
        )[:k]

    if not picked:
        return None, cross_channel_accept, clusters, "miss"
    return picked, cross_channel_accept, clusters, ""


def accept_from_picked(
    picked: list[tuple[int, float]],
    clusters: pd.DataFrame,
    cross_channel_accept: bool,
) -> KNNHit:
    """Stage 2: apply hard/soft accept logic to a picked neighbor list. Split
    out from query() so the bake-off can intervene between picking and
    accepting (the pool filter sits exactly there). Behavior matches the
    original inline path verbatim — see git history for the merged version."""
    labels = [lab for lab, _ in picked]
    cosines = [cos for _, cos in picked]
    top_rows = [clusters.iloc[int(lab)] for lab in labels]
    top1 = top_rows[0]
    top1_cos = float(cosines[0])
    top1_agree = float(top1.get("cluster_agreement_coicop", 0.0))

    topk_codes = [r.get("coicop_code") for r in top_rows]
    code_counter = Counter([c for c in topk_codes if c is not None])
    top_code, top_code_count = (None, 0)
    if code_counter:
        top_code, top_code_count = code_counter.most_common(1)[0]

    def _payload_from_cluster_row(r) -> dict:
        out = {}
        for f in (
            "coicop_code",
            "sub_label_id",
            "state",
            "pricing_basis",
            "standard_unit",
            "amount_value",
            "count",
            "multiplier",
            "is_promotion",
            "is_bundle",
            "is_multipack",
            "promo_reason",
            "confidence",
            "channel",
        ):
            if f in r.index:
                out[f] = r.get(f)
        out["cross_channel_accept"] = cross_channel_accept
        return out

    if (
        top1_cos >= config.KNN_TAU_HIGH
        and top1_agree >= config.KNN_CLUSTER_AGREEMENT_MIN
    ):
        return KNNHit(
            accepted=True,
            cluster_id=str(top1.get("cluster_id") or ""),
            payload=_payload_from_cluster_row(top1),
            top1_cosine=top1_cos,
            top1_cluster_agreement=top1_agree,
            topk_majority=int(top_code_count),
            escalation_reason="hard",
        )

    if (
        top_code is not None
        and top_code_count >= config.KNN_SOFT_MAJORITY_MIN
        and top1_cos >= config.KNN_TAU_LOW
    ):
        chosen = next(r for r in top_rows if r.get("coicop_code") == top_code)
        return KNNHit(
            accepted=True,
            cluster_id=str(chosen.get("cluster_id") or ""),
            payload=_payload_from_cluster_row(chosen),
            top1_cosine=top1_cos,
            top1_cluster_agreement=float(chosen.get("cluster_agreement_coicop", 0.0)),
            topk_majority=int(top_code_count),
            escalation_reason="soft",
        )

    return KNNHit(
        accepted=False,
        cluster_id=str(top1.get("cluster_id") or ""),
        payload={},
        top1_cosine=top1_cos,
        top1_cluster_agreement=top1_agree,
        topk_majority=int(top_code_count),
        escalation_reason="miss",
    )


def query(
    country: str,
    query_text: str,
    k: Optional[int] = None,
    channel: Optional[str] = None,
    category: Optional[str] = None,
) -> KNNHit:
    """Look up `query_text` against the country index. Returns a KNNHit with
    `accepted=True` only when the hard τ_high+agreement or soft majority+τ_low
    conditions are met. Otherwise accepted=False with an escalation reason.

    When ``channel`` is provided, K-NN is first filtered to same-channel
    cluster reps; if fewer than ``MIN_SAME_CHANNEL_KNN`` candidates clear the
    distance threshold, fall through to cross-channel candidates (logged via
    ``cross_channel_accept=True`` on the resulting payload).
    """
    picked, cross_channel_accept, clusters, reason = pick_neighbors(
        country,
        query_text,
        k=k,
        channel=channel,
        category=category,
    )
    if picked is None:
        return KNNHit(
            accepted=False,
            cluster_id="",
            payload={},
            top1_cosine=0.0,
            top1_cluster_agreement=0.0,
            topk_majority=0,
            escalation_reason=reason,
        )
    return accept_from_picked(picked, clusters, cross_channel_accept)


def reindex_all(cache_df: Optional[pd.DataFrame] = None) -> dict[str, int]:
    """Cluster, then build one index per country. Returns {country: n_clusters}
    for indices actually built (skipped countries omitted)."""
    if cache_df is None:
        from prices.enrich import cache as cache_mod

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
