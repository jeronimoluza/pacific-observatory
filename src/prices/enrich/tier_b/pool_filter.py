"""Tier-b KNN pool filter — restricts the candidate neighbor pool by COICOP class.

Two variants (hard-drop, rank-boost) plus the YAML-overrides-cache resolver.
Used by the bake-off harness to compare strategies; production wiring lands
after the bake-off picks a variant (see future ADR-0003). Pure module — no
I/O, no global state.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional

import pandas as pd


def class_prefix(code: str) -> str:
    if not isinstance(code, str) or len(code) < 4:
        return ""
    return code[:4]


def class_prefixes(codes: Iterable[str]) -> set[str]:
    return {p for p in (class_prefix(c) for c in codes or ()) if p}


def is_narrow(codes: Iterable[str]) -> bool:
    """Narrowness rule γ (ADR-0002): codes share a single 3-digit class prefix."""
    return len(class_prefixes(codes)) == 1


def compute_channel_derived_codes(
    cluster_df: pd.DataFrame,
    country: str,
    channel: str,
    threshold: float = 0.05,
) -> list[str]:
    """3-digit class prefixes that account for ≥ threshold of clusters in this
    (country, channel). Below-threshold codes are dropped as long-tail noise —
    a supermarket with 0.3% mass on '11.1' (cafés) shouldn't admit cafés to its
    KNN pool."""
    if cluster_df.empty:
        return []
    sub = cluster_df[
        (cluster_df.get("country") == country) & (cluster_df.get("channel") == channel)
    ]
    codes = [c for c in sub.get("coicop_code", []) if isinstance(c, str) and c]
    if not codes:
        return []
    counts = Counter(class_prefix(c) for c in codes)
    counts.pop("", None)
    total = sum(counts.values())
    if total == 0:
        return []
    return [p for p, c in counts.items() if c / total >= threshold]


def resolve_filter_codes(
    yaml_codes: Optional[list[str]],
    cache_derived: Iterable[str],
) -> set[str]:
    """Hybrid: YAML declaration wins when non-empty; otherwise fall back to
    cache-derived. Empty result means "no filter" — caller treats as bypass."""
    if yaml_codes:
        return class_prefixes(yaml_codes)
    return set(cache_derived)


def apply_hard_drop(
    picked: list[tuple[int, float]],
    cluster_codes: dict[int, str],
    allowed_prefixes: set[str],
) -> list[tuple[int, float]]:
    """Remove candidates whose code prefix is not in allowed_prefixes."""
    if not allowed_prefixes:
        return picked
    return [
        (lab, cos)
        for lab, cos in picked
        if class_prefix(cluster_codes.get(lab, "")) in allowed_prefixes
    ]


def apply_rank_boost(
    picked: list[tuple[int, float]],
    cluster_codes: dict[int, str],
    allowed_prefixes: set[str],
    boost: float = 0.05,
) -> list[tuple[int, float]]:
    """Add `boost` to in-set candidates' cosine, then re-sort descending. Keeps
    out-of-set neighbors as fallback when the query's true code is genuinely
    outside the declared set. Default boost is heuristic; bake-off may revise."""
    if not allowed_prefixes:
        return picked
    adjusted = [
        (
            lab,
            cos
            + (
                boost
                if class_prefix(cluster_codes.get(lab, "")) in allowed_prefixes
                else 0.0
            ),
        )
        for lab, cos in picked
    ]
    return sorted(adjusted, key=lambda x: x[1], reverse=True)
