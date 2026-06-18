"""Tier-b cluster resolution: group cache rows by canonical product identity
and resolve a single label per cluster via majority vote.

Split out of index.py to keep that module under the 500-line cap. The KNNHit
record lives here too (it is the cluster-lookup result type). No logic change
versus the pre-split index.py.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from prices.enrich.normalize import canonicalize, resolve_cluster_category

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
