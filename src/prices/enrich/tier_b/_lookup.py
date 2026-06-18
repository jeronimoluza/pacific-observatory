"""Tier-b query path: HNSW lookup + same-channel filter (pick_neighbors) and
the hard/soft accept logic (accept_from_picked / query).

Split out of index.py to keep that module under the 500-line cap. No logic
change versus the pre-split index.py — the accept thresholds, exclude block,
and sub_label co-gate are byte-identical.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

import pandas as pd

from prices.enrich import config
from prices.enrich.normalize import normalize_breadcrumb
from prices.enrich.tier_b import _anchors
from prices.enrich.tier_b._cluster import KNNHit
from prices.enrich.tier_b._store import _get_index
from prices.enrich.tier_b.embed import embed_texts


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
    phrases = _anchors.excludes().get(str(coicop_code), [])
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
