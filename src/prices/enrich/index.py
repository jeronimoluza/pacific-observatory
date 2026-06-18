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
import re
import unicodedata
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

_COICOP_DIR = Path(__file__).resolve().parent / "keywords" / "coicop"
_ANCHORS_DF: Optional[pd.DataFrame] = None
_EXCLUDES: dict[str, list[str]] = {}
_REDIRECTS: dict[str, list[str]] = {}


def _load_anchors() -> pd.DataFrame:
    p = _COICOP_DIR / "_sub_labels.parquet"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_parquet(p)
    # Include both anchor and synonym rows: synonym rows carry verbatim JSON ids
    # that match real-cluster sub_label_id values, closing the vocabulary gap.
    return df[df["role"].isin(["anchor", "synonym"])].copy()


def _load_excludes() -> dict[str, list[str]]:
    p = _COICOP_DIR / "_excludes.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p)
    out: dict[str, list[str]] = {}
    for code, grp in df.groupby("coicop_code"):
        out[str(code)] = grp["phrase"].astype(str).tolist()
    return out


def _load_redirects() -> dict[str, list[str]]:
    """Inverse of _load_excludes: map each `excluded_code` (the redirect TARGET)
    to the unique phrases that should pull queries toward it.

    The COICOP authority's excludes are bidirectional information: leaf A says
    'phrase P really belongs at leaf B'. _load_excludes uses the A side as a
    post-retrieval block; this loader uses the B side as embedding-time
    vocabulary so the cosine pulls toward B in the first place.
    """
    p = _COICOP_DIR / "_excludes.parquet"
    if not p.exists():
        return {}
    df = pd.read_parquet(p)
    df = df[df["excluded_code"].notna() & (df["excluded_code"].astype(str) != "")]
    out: dict[str, list[str]] = {}
    for code, grp in df.groupby("excluded_code"):
        phrases: list[str] = []
        seen = set()
        for ph in grp["phrase"].astype(str).tolist():
            key = ph.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            phrases.append(ph.strip())
        if phrases:
            out[str(code)] = phrases
    return out


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60]


def _init_module_data() -> None:
    global _ANCHORS_DF, _EXCLUDES, _REDIRECTS
    _ANCHORS_DF = _load_anchors()
    _EXCLUDES = _load_excludes()
    _REDIRECTS = _load_redirects()


_init_module_data()


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


def _make_anchor_rows(country: str) -> pd.DataFrame:
    """Build synthetic anchor rows for one country from the loaded anchors DF.
    `sub_label_id` is read directly from the parquet `id` column so anchor IDs
    match the real-cluster vocabulary (both originate from coicop_subcategories.json ids).

    Synonyms fold into one row per (coicop_code, sub_label_id): all labels for
    the same id concatenate into the passage text so e5 sees a denser semantic
    surface (e.g. "Whisky · bourbon · rye whiskey · scotch · single malt").
    """
    if _ANCHORS_DF is None or _ANCHORS_DF.empty:
        return pd.DataFrame()
    has_id_col = "id" in _ANCHORS_DF.columns
    rows = []
    if has_id_col:
        for (code, sl), grp in _ANCHORS_DF.groupby(["coicop_code", "id"], sort=False):
            code = str(code)
            sl = str(sl)
            labels = [str(x) for x in grp["label"].tolist() if str(x).strip()]
            seen = set()
            uniq_labels = []
            for lab in labels:
                key = lab.lower()
                if key in seen:
                    continue
                seen.add(key)
                uniq_labels.append(lab)
            primary = uniq_labels[0] if uniq_labels else sl
            passage = " · ".join(uniq_labels) if uniq_labels else primary
            rows.append(
                {
                    "cluster_id": f"_anchor::{country}::{code}::{sl}",
                    "country": country,
                    "channel": "_anchor",
                    "canonical_strict": passage.lower(),
                    "representative_name": passage,
                    "rep_category": "",
                    "cluster_size": 1,
                    "cluster_agreement_coicop": 1.0,
                    "cluster_agreement_sub_label": 1.0,
                    "coicop_code": code,
                    "sub_label_id": sl,
                    "state": "anchor",
                    "pricing_basis": None,
                    "standard_unit": None,
                    "amount_value": None,
                    "count": 0,
                    "multiplier": None,
                    "is_promotion": False,
                    "is_bundle": False,
                    "is_multipack": False,
                    "promo_reason": None,
                    "confidence": 1.0,
                }
            )
    else:
        for _, r in _ANCHORS_DF.iterrows():
            code = str(r["coicop_code"])
            label = str(r["label"])
            sl = _slug(label)
            rows.append(
                {
                    "cluster_id": f"_anchor::{country}::{code}::{sl}",
                    "country": country,
                    "channel": "_anchor",
                    "canonical_strict": label.lower(),
                    "representative_name": label,
                    "rep_category": "",
                    "cluster_size": 1,
                    "cluster_agreement_coicop": 1.0,
                    "cluster_agreement_sub_label": 1.0,
                    "coicop_code": code,
                    "sub_label_id": sl,
                    "state": "anchor",
                    "pricing_basis": None,
                    "standard_unit": None,
                    "amount_value": None,
                    "count": 0,
                    "multiplier": None,
                    "is_promotion": False,
                    "is_bundle": False,
                    "is_multipack": False,
                    "promo_reason": None,
                    "confidence": 1.0,
                }
            )
    # Redirect anchors: phrases excluded from leaf A and pointed at leaf B
    # become embedding vocabulary on B. sub_label_id="_redirect" — downstream
    # routes to partial_sub_label_pending so tier-c settles the fine label.
    for code, phrases in _REDIRECTS.items():
        passage = " · ".join(phrases)
        rows.append(
            {
                "cluster_id": f"_redirect::{country}::{code}",
                "country": country,
                "channel": "_anchor",
                "canonical_strict": passage.lower(),
                "representative_name": passage,
                "rep_category": "",
                "cluster_size": 1,
                "cluster_agreement_coicop": 1.0,
                "cluster_agreement_sub_label": 0.0,
                "coicop_code": str(code),
                "sub_label_id": "_redirect",
                "state": "anchor",
                "pricing_basis": None,
                "standard_unit": None,
                "amount_value": None,
                "count": 0,
                "multiplier": None,
                "is_promotion": False,
                "is_bundle": False,
                "is_multipack": False,
                "promo_reason": None,
                "confidence": 1.0,
            }
        )
    return pd.DataFrame(rows)


def build_index(cluster_df: pd.DataFrame, country: str) -> Optional[hnswlib.Index]:
    """Build a cosine hnswlib index for one country. Returns None if the
    country falls below KNN_BOOTSTRAP_CLUSTER_FLOOR (real clusters only)."""
    sub = cluster_df[cluster_df["country"] == country].copy()
    if len(sub) < config.KNN_BOOTSTRAP_CLUSTER_FLOOR:
        return None
    anchor_rows = _make_anchor_rows(country)
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
    _meta_path(country).write_text(
        json.dumps(
            {
                "dim": config.EMBED_DIM,
                "backend": config.EMBED_BACKEND,
                "n_clusters": n_real,
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
    n_real = (
        int((clusters["channel"] != "_anchor").sum())
        if "channel" in clusters.columns
        else len(clusters)
    )
    if n_real < config.KNN_BOOTSTRAP_CLUSTER_FLOOR:
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
            # _anchor rows are universally matchable — never filtered to "other"
            if str(row_channel) == channel or str(row_channel) == "_anchor":
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


def _sub_label_query_agreement(
    rows: list, accepted_code: object, chosen_sub_label: object
) -> float:
    """Fraction of query-time neighbors that (a) share the accepted coicop_code
    AND (b) carry the same sub_label_id as the chosen row. Returns 0.0 when no
    same-coicop neighbors exist or the chosen sub_label is null."""
    if chosen_sub_label is None or accepted_code is None:
        return 0.0
    same_coicop = [r for r in rows if r.get("coicop_code") == accepted_code]
    if not same_coicop:
        return 0.0
    n_match = sum(1 for r in same_coicop if r.get("sub_label_id") == chosen_sub_label)
    return n_match / len(same_coicop)


def _is_excluded(coicop_code: object, query_text: str) -> bool:
    """Return True if any exclude phrase for this code is a substring of query_text."""
    if not coicop_code or not query_text:
        return False
    phrases = _EXCLUDES.get(str(coicop_code), [])
    qt_lower = query_text.lower()
    return any(p in qt_lower for p in phrases)


def _miss_snapshot(top1, cross_channel_accept: bool) -> dict:
    """Bare minimum of top1 fields kept on miss returns so apply_brand_prior
    can borrow tier-b's top1 sub_label when its coicop matches the prior."""
    return {
        "_top1_coicop_code": top1.get("coicop_code"),
        "_top1_sub_label_id": top1.get("sub_label_id"),
        "cross_channel_accept": cross_channel_accept,
    }


def accept_from_picked(
    picked: list[tuple[int, float]],
    clusters: pd.DataFrame,
    cross_channel_accept: bool,
    query_text: str = "",
) -> KNNHit:
    """Stage 2: apply hard/soft accept logic to a picked neighbor list. Split
    out from query() so the bake-off can intervene between picking and
    accepting (the pool filter sits exactly there).

    Sub_label_id co-gate (Phase 3, 2026-06-11): when the coicop accept lands
    but the K same-coicop neighbors disagree on sub_label_id below
    `KNN_SUB_LABEL_AGREEMENT_MIN`, return a hit with the coicop accepted but
    `sub_label_id` cleared and `escalation_reason='partial_sub_label_pending'`
    so the cascade routes the row to a constrained tier-c call instead of
    writing the cluster's sub_label_id straight through."""
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

    def _maybe_partial(chosen_row, base_reason: str) -> tuple[dict, str]:
        """Return (payload, escalation_reason). If the K same-coicop neighbors
        disagree on sub_label_id below the gate, blank `sub_label_id` and
        flag for constrained tier-c."""
        payload = _payload_from_cluster_row(chosen_row)
        chosen_sub_label = chosen_row.get("sub_label_id")
        accepted_code = chosen_row.get("coicop_code")
        sub_agree = _sub_label_query_agreement(
            top_rows, accepted_code, chosen_sub_label
        )
        payload["sub_label_query_agreement"] = sub_agree
        if (
            chosen_sub_label is not None
            and sub_agree < config.KNN_SUB_LABEL_AGREEMENT_MIN
        ):
            payload["sub_label_id"] = None
            return payload, "partial_sub_label_pending"
        return payload, base_reason

    if (
        top1_cos >= config.knn_score_hard_min(config.E5_MODEL_PATH)
        and top1_agree >= config.KNN_CLUSTER_AGREEMENT_MIN
    ):
        if not _is_excluded(top1.get("coicop_code"), query_text):
            payload, reason = _maybe_partial(top1, "hard")
            return KNNHit(
                accepted=True,
                cluster_id=str(top1.get("cluster_id") or ""),
                payload=payload,
                top1_cosine=top1_cos,
                top1_cluster_agreement=top1_agree,
                topk_majority=int(top_code_count),
                escalation_reason=reason,
            )
        # hard candidate excluded — fall through to soft check on remaining rows
        for row, cos in zip(top_rows[1:], cosines[1:]):
            row_code = row.get("coicop_code")
            row_agree = float(row.get("cluster_agreement_coicop", 0.0))
            if (
                cos >= config.knn_score_hard_min(config.E5_MODEL_PATH)
                and row_agree >= config.KNN_CLUSTER_AGREEMENT_MIN
                and not _is_excluded(row_code, query_text)
            ):
                payload, reason = _maybe_partial(row, "hard")
                return KNNHit(
                    accepted=True,
                    cluster_id=str(row.get("cluster_id") or ""),
                    payload=payload,
                    top1_cosine=top1_cos,
                    top1_cluster_agreement=row_agree,
                    topk_majority=int(top_code_count),
                    escalation_reason=reason,
                )

    # HIGH-COS override (2026-06-16). Rare-but-clean cluster: a single nearby
    # neighbor with very-high cosine AND near-perfect cluster_agreement_coicop
    # is accepted even when the K-NN majority floor isn't met. Catches the
    # Spring-Onion-style case (top1 cos=0.887, agreement=1.0, maj=2/5).
    if (
        getattr(config, "KNN_HIGH_COS_OVERRIDE_ENABLED", False)
        and top1_cos >= config.KNN_HIGH_COS_OVERRIDE_COSINE
        and top1_agree >= config.KNN_HIGH_COS_OVERRIDE_AGREEMENT
        and not _is_excluded(top1.get("coicop_code"), query_text)
    ):
        payload, reason = _maybe_partial(top1, "high_cos_override")
        return KNNHit(
            accepted=True,
            cluster_id=str(top1.get("cluster_id") or ""),
            payload=payload,
            top1_cosine=top1_cos,
            top1_cluster_agreement=top1_agree,
            topk_majority=int(top_code_count),
            escalation_reason=reason,
        )

    if (
        top_code is not None
        and top_code_count >= config.KNN_SOFT_MAJORITY_MIN
        and top1_cos >= config.KNN_TAU_LOW
    ):
        if not _is_excluded(top_code, query_text):
            chosen = next(r for r in top_rows if r.get("coicop_code") == top_code)
            payload, reason = _maybe_partial(chosen, "soft")
            return KNNHit(
                accepted=True,
                cluster_id=str(chosen.get("cluster_id") or ""),
                payload=payload,
                top1_cosine=top1_cos,
                top1_cluster_agreement=float(
                    chosen.get("cluster_agreement_coicop", 0.0)
                ),
                topk_majority=int(top_code_count),
                escalation_reason=reason,
            )
        # soft majority code excluded — try next majority code
        for alt_code, alt_count in code_counter.most_common()[1:]:
            if alt_count < config.KNN_SOFT_MAJORITY_MIN:
                break
            if _is_excluded(alt_code, query_text):
                continue
            chosen = next(
                (r for r in top_rows if r.get("coicop_code") == alt_code), None
            )
            if chosen is None:
                continue
            payload, reason = _maybe_partial(chosen, "soft")
            return KNNHit(
                accepted=True,
                cluster_id=str(chosen.get("cluster_id") or ""),
                payload=payload,
                top1_cosine=top1_cos,
                top1_cluster_agreement=float(
                    chosen.get("cluster_agreement_coicop", 0.0)
                ),
                topk_majority=int(alt_count),
                escalation_reason=reason,
            )
        return KNNHit(
            accepted=False,
            cluster_id=str(top1.get("cluster_id") or ""),
            payload=_miss_snapshot(top1, cross_channel_accept),
            top1_cosine=top1_cos,
            top1_cluster_agreement=top1_agree,
            topk_majority=int(top_code_count),
            escalation_reason="excluded",
        )

    return KNNHit(
        accepted=False,
        cluster_id=str(top1.get("cluster_id") or ""),
        payload=_miss_snapshot(top1, cross_channel_accept),
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
    return accept_from_picked(
        picked, clusters, cross_channel_accept, query_text=query_text
    )


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
