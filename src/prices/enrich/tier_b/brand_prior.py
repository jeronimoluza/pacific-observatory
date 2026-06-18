"""Tier-b residual rescue via brand whitelist.

Lives outside index.py to keep that file from growing further past the
500-LoC project cap. Cascade imports `apply_brand_prior`; the helper reads
`static/brand_priors.yaml` lazily and caches it at module level.
"""

from __future__ import annotations

from typing import Optional

from prices.enrich import config
from prices.enrich.tier_b.index import KNNHit


_BRAND_PRIORS_CACHE: Optional[dict[str, dict]] = None


def _load_brand_priors() -> dict[str, dict]:
    global _BRAND_PRIORS_CACHE
    if _BRAND_PRIORS_CACHE is not None:
        return _BRAND_PRIORS_CACHE
    path = getattr(config, "BRAND_PRIORS_PATH", None)
    if path is None or not path.exists():
        _BRAND_PRIORS_CACHE = {}
        return _BRAND_PRIORS_CACHE
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for k, v in raw.items():
        if str(k).startswith("_"):
            continue
        if not isinstance(v, dict) or "coicop" not in v:
            continue
        out[str(k).lower()] = {"coicop": str(v["coicop"]), "note": v.get("note", "")}
    _BRAND_PRIORS_CACHE = out
    return out


def reload_brand_priors() -> None:
    """Force-reload the brand_priors.yaml cache. For tests and the cascade
    long-running loop after a YAML edit."""
    global _BRAND_PRIORS_CACHE
    _BRAND_PRIORS_CACHE = None


def apply_brand_prior(hit: KNNHit, brand: Optional[str]) -> Optional[KNNHit]:
    """Rescue a tier-b miss when the normalized brand sits in the whitelist
    and top1_cosine is in the pre-soft band [BRAND_PRIOR_COS_LOW,
    BRAND_PRIOR_COS_HIGH). Returns a fresh accepted KNNHit on rescue or
    None when the prior does not apply (caller keeps the original hit).

    Sub_label_id is borrowed from tier-b's top1 only when its coicop matches
    the prior; otherwise blanked and routed to constrained tier-c.
    """
    if not getattr(config, "BRAND_PRIOR_ENABLED", False):
        return None
    if hit.accepted or not brand:
        return None
    cos = hit.top1_cosine
    if cos < config.BRAND_PRIOR_COS_LOW or cos >= config.BRAND_PRIOR_COS_HIGH:
        return None
    priors = _load_brand_priors()
    entry = priors.get(str(brand).lower())
    if entry is None:
        return None
    prior_coicop = entry["coicop"]
    snap = hit.payload or {}
    top1_coicop = snap.get("_top1_coicop_code")
    top1_sub = snap.get("_top1_sub_label_id")
    sub_label = top1_sub if top1_coicop == prior_coicop else None
    return KNNHit(
        accepted=True,
        cluster_id=hit.cluster_id,
        payload={
            "coicop_code": prior_coicop,
            "sub_label_id": sub_label,
            "brand_prior": brand,
            "brand_prior_note": entry.get("note", ""),
            "cross_channel_accept": bool(snap.get("cross_channel_accept", False)),
        },
        top1_cosine=cos,
        top1_cluster_agreement=hit.top1_cluster_agreement,
        topk_majority=hit.topk_majority,
        escalation_reason="brand_prior",
    )
