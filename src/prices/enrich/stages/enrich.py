"""Match cascade — formerly the per-observation enrichment runner.

Runs the 5-tier cascade over the products dimension. Each tier writes to
`match_log.parquet` with a `match_method` so coverage is auditable.

Tiers:
    0. input_hash exact match against cache (legacy fallback)
    1. product_identity_key exact match
    2. (canonical_loose, country) exact match
    a. regex structural extraction (tier_a — overlays, doesn't decide)
    b. KNN over cluster-resolved cache (tier_b)
    c. KNN-aware LLM reranker (tier_c — residual products only; in `stages/tier_c.py`)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from prices.enrich import cache, config, cross_check, pool_filter
from prices.enrich import index as tier_b_index
from prices.enrich.brand_prior import apply_brand_prior
from prices.enrich.extract import StructuralFields, extract
from prices.enrich.narrowness import is_narrow, parse_codes, resolved_code
from prices.enrich.propagation import product_input_hashes, propagate_row
from prices.enrich.stages import tier_c

_STRUCTURAL_FIELDS = (
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "promo_reason",
)

_LANG_MAP_CACHE: Optional[dict[str, str]] = None


def _resolve_lang(country: str) -> Optional[str]:
    """Resolve primary language for a country slug via countries.yaml. Lazy
    module-level cache; returns None if country slug missing or yaml absent."""
    global _LANG_MAP_CACHE
    if _LANG_MAP_CACHE is None:
        try:
            from core.config import load_countries

            mp: dict[str, str] = {}
            for slug, meta in load_countries().items():
                langs = meta.get("languages") or []
                if langs:
                    mp[slug] = langs[0]
            _LANG_MAP_CACHE = mp
        except Exception:
            _LANG_MAP_CACHE = {}
    return _LANG_MAP_CACHE.get(country)


_CLUSTER_GATED_FIELDS = ("pricing_basis", "standard_unit")


def _overlay_tier_a(
    payload: dict, sf: StructuralFields, cluster_agreement_coicop: float = 0.0
) -> dict:
    """Tier (a) overlays non-None structural fields onto payload.

    `pricing_basis` and `standard_unit` are gated: when the source comes from a
    strongly-agreeing tier-b cluster (`cluster_agreement_coicop ≥
    KNN_CLUSTER_AGREEMENT_MIN`) AND already carries a value, the cluster vote
    wins. Per-row fields (amount, count, promos, multipack) always overlay.
    """
    out = dict(payload)
    cluster_strong = cluster_agreement_coicop >= config.KNN_CLUSTER_AGREEMENT_MIN
    for f in _STRUCTURAL_FIELDS:
        val = getattr(sf, f)
        if val is None:
            continue
        if f in _CLUSTER_GATED_FIELDS and cluster_strong and out.get(f) is not None:
            continue
        out[f] = val
    return out


def _tier_a_fired(sf: StructuralFields) -> bool:
    return any(getattr(sf, f) is not None for f in _STRUCTURAL_FIELDS)


def _pricing_basis_mismatch(tier_a: StructuralFields, source: dict) -> bool:
    """True only when tier-a extracted a pricing_basis AND the tier-b source
    carries a different non-null pricing_basis. Either side null → no mismatch."""
    a = tier_a.pricing_basis
    b = source.get("pricing_basis")
    if a is None or b is None:
        return False
    return a != b


_CACHE_DERIVED_PREFIXES: Optional[dict[tuple[str, str], list[str]]] = None


def _cache_derived_prefixes(country: str, channel: str) -> list[str]:
    """Lazy-load (country, channel) → cache-derived 3-digit prefix list from
    `clusters_<country>.parquet` files. Used by the tier-b pool filter when no
    YAML codes are declared. Cached at module level; one-time disk read."""
    global _CACHE_DERIVED_PREFIXES
    if _CACHE_DERIVED_PREFIXES is None:
        out: dict[tuple[str, str], list[str]] = {}
        if config.TIER_B_INDEX_DIR.exists():
            for cp in config.TIER_B_INDEX_DIR.glob("clusters_*.parquet"):
                country_slug = cp.stem.removeprefix("clusters_")
                try:
                    df = pd.read_parquet(cp)
                except Exception:
                    continue
                if "channel" not in df.columns:
                    continue
                for ch in df["channel"].dropna().unique():
                    codes = pool_filter.compute_channel_derived_codes(
                        df, country_slug, str(ch)
                    )
                    if codes:
                        out[(country_slug, str(ch))] = codes
        _CACHE_DERIVED_PREFIXES = out
    return _CACHE_DERIVED_PREFIXES.get((country, channel), [])


def _tier_b_dispatch(
    country: str,
    query_text: str,
    channel_arg: Optional[str],
    category: Optional[str],
    product,
) -> tier_b_index.KNNHit:
    """Tier-b call site with optional pool filter (Feature B, ADR-0003).
    Falls back to the existing `query()` path when the filter is off or the
    allowed-prefix set is empty — production behavior is unchanged by default."""
    declared = parse_codes(product.get("declared_coicop_codes"))
    cache_derived: list[str] = []
    if not declared:
        cache_derived = _cache_derived_prefixes(country, channel_arg or "null")
    allowed = pool_filter.resolve_filter_codes(declared, cache_derived)
    mode = getattr(config, "TIER_B_POOL_FILTER", "off")
    if mode == "off" or not allowed:
        return tier_b_index.query(
            country=country,
            query_text=query_text,
            channel=channel_arg,
            category=category,
        )
    picked, cross, clusters_df, reason = tier_b_index.pick_neighbors(
        country=country,
        query_text=query_text,
        channel=channel_arg,
        category=category,
    )
    if picked is None or clusters_df is None:
        return tier_b_index.KNNHit(
            accepted=False,
            cluster_id="",
            payload={},
            top1_cosine=0.0,
            top1_cluster_agreement=0.0,
            topk_majority=0,
            escalation_reason=reason,
        )
    cluster_codes = {
        lab: str(clusters_df.iloc[lab].get("coicop_code") or "") for lab, _ in picked
    }
    if mode == "hard_drop":
        filtered = pool_filter.apply_hard_drop(picked, cluster_codes, allowed)
    elif mode == "rank_boost":
        boost = getattr(config, "POOL_FILTER_BOOST", 0.05)
        filtered = pool_filter.apply_rank_boost(
            picked, cluster_codes, allowed, boost=boost
        )
    else:
        filtered = picked
    if not filtered:
        return tier_b_index.KNNHit(
            accepted=False,
            cluster_id="",
            payload={},
            top1_cosine=0.0,
            top1_cluster_agreement=0.0,
            topk_majority=0,
            escalation_reason="miss_after_filter",
        )
    return tier_b_index.accept_from_picked(filtered, clusters_df, cross)


_KILLSWITCH_CACHE: Optional[set[tuple[str, str]]] = None


def _killswitch_combos() -> set[tuple[str, str]]:
    """Load the (country, channel) combos whose tier-b precision is below the
    eval-measured floor. Combos in the set are forced to tier-c instead of
    accepting a tier-b hit. Cached at module level."""
    global _KILLSWITCH_CACHE
    if _KILLSWITCH_CACHE is not None:
        return _KILLSWITCH_CACHE
    if not config.TIER_B_KILLSWITCH_ENABLED:
        _KILLSWITCH_CACHE = set()
        return _KILLSWITCH_CACHE
    try:
        import yaml

        data = yaml.safe_load(config.TIER_B_KILLSWITCH_PATH.read_text(encoding="utf-8"))
        _KILLSWITCH_CACHE = {
            (str(c["country"]), str(c["channel"])) for c in (data.get("combos") or [])
        }
    except (FileNotFoundError, KeyError, TypeError):
        _KILLSWITCH_CACHE = set()
    return _KILLSWITCH_CACHE


_PAYLOAD_FIELDS = [
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "dimensions_json",
    "coicop_code",
    "sub_label_id",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "promo_reason",
    "confidence",
    "state",
]


def _build_cache_lookups(
    cached: pd.DataFrame,
) -> tuple[dict[str, dict], dict[str, dict], dict[tuple[str, str], dict]]:
    """Return (input_hash, product_identity_key, (canonical_loose, country)) lookups
    over the cache. Legacy rows without pid/loose columns simply omit those entries."""
    hash_lookup: dict[str, dict] = {}
    pid_lookup: dict[str, dict] = {}
    loose_lookup: dict[tuple[str, str], dict] = {}
    if cached.empty:
        return hash_lookup, pid_lookup, loose_lookup
    has_pid = "product_identity_key" in cached.columns
    has_loose = "canonical_loose" in cached.columns
    has_country = "country" in cached.columns
    for r in cached.to_dict(orient="records"):
        h = r.get("input_hash")
        if isinstance(h, str) and h:
            hash_lookup.setdefault(h, r)
        if has_pid:
            pid = r.get("product_identity_key")
            if isinstance(pid, str) and pid:
                pid_lookup.setdefault(pid, r)
        if has_loose and has_country:
            loose = r.get("canonical_loose")
            country = r.get("country")
            if (
                isinstance(loose, str)
                and loose
                and isinstance(country, str)
                and country
            ):
                loose_lookup.setdefault((loose, country), r)
    return hash_lookup, pid_lookup, loose_lookup


def _payload_from_source(src: dict) -> dict:
    return {k: src.get(k) for k in _PAYLOAD_FIELDS}


def cascade(
    products: pd.DataFrame, cached: pd.DataFrame
) -> tuple[list[dict], pd.DataFrame, list[dict], list[dict]]:
    """Pure cascade — no I/O, no LLM. Returns (cache_rows_to_write, residual_products, match_log_rows, cross_check_rows).

    `cache_rows_to_write` covers Tier 0/1/2/b propagations. `residual_products`
    is what falls through to tier (c) (LLM)."""
    hash_lookup, pid_lookup, loose_lookup = _build_cache_lookups(cached)
    now = datetime.now(timezone.utc).isoformat()
    cache_rows: list[dict] = []
    match_log: list[dict] = []
    cross_check_rows: list[dict] = []
    residual_idx: list[int] = []
    tier_a_by_idx: dict = {}

    for idx, product in products.iterrows():
        pid = product.get("product_identity_key")
        country = str(product.get("country") or "")
        loose = product.get("canonical_loose")
        input_hashes = product_input_hashes(product)

        # Tier (a) — regex structural extraction. Runs unconditionally; result
        # is overlaid onto whatever subsequent tier resolves, and also stamped
        # onto the residual DataFrame as `tier_a_*` columns for the LLM tier.
        lang = _resolve_lang(country)
        tier_a = extract(
            item_name=str(product.get("first_name") or ""),
            category=(str(product.get("category") or "") or None),
            country=country,
            lang=lang,
        )
        tier_a_by_idx[idx] = tier_a
        tier_a_suffix = "+regex" if _tier_a_fired(tier_a) else ""

        source: Optional[dict] = None
        method: Optional[str] = None

        # Tier 0: input_hash
        for h in input_hashes:
            if h in hash_lookup:
                source = hash_lookup[h]
                method = "input_hash"
                break

        # Tier 1: product_identity_key
        if source is None and isinstance(pid, str) and pid in pid_lookup:
            source = pid_lookup[pid]
            method = "product_identity_key"

        # Tier 2: (canonical_loose, country)
        if source is None and isinstance(loose, str) and loose and country:
            key = (loose, country)
            if key in loose_lookup:
                source = loose_lookup[key]
                method = "canonical_loose"

        # Source-curated short-circuit (ADR-0002). For narrow spider sources —
        # those whose YAML declares `coicop_codes:` sharing a single 3-digit
        # COICOP class prefix — bypass tier-b/c entirely. Tier-a regex has
        # already populated structural fields above.
        if source is None:
            declared = parse_codes(product.get("declared_coicop_codes"))
            if declared and is_narrow(declared):
                code = resolved_code(declared)
                payload = _overlay_tier_a(
                    {
                        "pricing_basis": None,
                        "amount_value": None,
                        "standard_unit": None,
                        "count": None,
                        "multiplier": None,
                        "dimensions_json": None,
                        "coicop_code": code,
                        "sub_label_id": None,
                        "is_promotion": None,
                        "is_bundle": None,
                        "is_multipack": None,
                        "promo_reason": None,
                        "confidence": 1.0,
                        "state": "resolved",
                    },
                    tier_a,
                    cluster_agreement_coicop=0.0,
                )
                # Phase-2 consolidation on the source-curated path.
                sc_bucket, sc_override = cross_check.consolidate(
                    payload.get("pricing_basis"),
                    str(payload.get("coicop_code") or ""),
                    payload.get("sub_label_id"),
                )
                if sc_bucket == "SILENT_OVERRIDE" and sc_override:
                    payload["pricing_basis"] = sc_override
                    # Leaf-gate B-reset: tier-a's amount/unit belonged to the
                    # wrong basis, so they cannot be trusted under the new one.
                    # Clobber to canonical defaults; count/multiplier are
                    # basis-orthogonal and stay as tier-a captured them.
                    payload["amount_value"] = None
                    payload["standard_unit"] = cross_check.canonical_unit_for_basis(
                        sc_override
                    )
                sc_suffix = ""
                if sc_bucket == "SILENT_OVERRIDE":
                    sc_suffix = "_basis_override"
                elif sc_bucket == "ESCALATE_MULTI":
                    sc_suffix = "_basis_pending"
                method_out = f"source_curated{tier_a_suffix}{sc_suffix}"
                for h in input_hashes:
                    if h in hash_lookup:
                        continue
                    cache_rows.append(
                        propagate_row(
                            h,
                            product,
                            payload,
                            method_out,
                            "",
                            0,
                            "source_curated",
                            now,
                        )
                    )
                match_log.append(
                    {
                        "product_identity_key": str(pid)
                        if isinstance(pid, str)
                        else "",
                        "canonical_loose": str(loose) if isinstance(loose, str) else "",
                        "country": country,
                        "n_input_hashes": len(input_hashes),
                        "match_method": method_out,
                        "matched_at": now,
                    }
                )
                cross_check_rows.append(
                    cross_check.build_row(
                        row_id=str(pid) if isinstance(pid, str) else (str(loose) or ""),
                        country=country,
                        structural_basis=payload.get("pricing_basis"),
                        categorical_code=str(payload.get("coicop_code") or ""),
                        categorical_sub_label=payload.get("sub_label_id"),
                        matched_at=now,
                        consolidation_bucket=sc_bucket,
                    )
                )
                continue

        # Tier (b): KNN over cluster-resolved cache. Falls through silently
        # when no index exists for the country (bootstrap or pre-build).
        if source is None and config.MATCH_TIER_B_ENABLED:
            row_channel = product.get("channel")
            channel_arg = (
                str(row_channel)
                if isinstance(row_channel, str) and row_channel
                else None
            )
            hit = _tier_b_dispatch(
                country=country,
                query_text=str(product.get("first_name") or ""),
                channel_arg=channel_arg,
                category=(str(product.get("category") or "") or None),
                product=product,
            )
            # Brand-prior rescue (2026-06-16). Only fires when tier-b returned
            # not-accepted, the normalized brand is whitelisted, and top1
            # cosine sits in the pre-soft band — see index.apply_brand_prior.
            if not hit.accepted:
                rescued = apply_brand_prior(hit, product.get("brand"))
                if rescued is not None:
                    hit = rescued
            killswitched = (
                hit.accepted
                and hit.escalation_reason != "brand_prior"
                and channel_arg is not None
                and (country, channel_arg) in _killswitch_combos()
            )
            # Phase-2 guarded basis-mismatch refusal. When tier-a and the
            # cluster disagree on pricing_basis, we previously refused
            # outright (almonds→wine guard). Phase-2 keeps that refusal ONLY
            # when allowed_bases is permissive — i.e. the rule book can't
            # confirm the cluster's category. When allowed_bases vouches for
            # the cluster (CLEAN/SILENT_OVERRIDE), we accept and let the
            # post-overlay consolidation arbitrate the basis.
            basis_mismatch_unguarded = False
            if (
                hit.accepted
                and not killswitched
                and _pricing_basis_mismatch(tier_a, hit.payload)
            ):
                pre_bucket, _ = cross_check.consolidate(
                    hit.payload.get("pricing_basis"),
                    str(hit.payload.get("coicop_code") or ""),
                    hit.payload.get("sub_label_id"),
                )
                if pre_bucket == "PASS_THROUGH":
                    basis_mismatch_unguarded = True
            if basis_mismatch_unguarded:
                tier_b_index.append_miss(
                    {
                        "cluster_id": hit.cluster_id,
                        "country": country,
                        "first_name": str(product.get("first_name") or ""),
                        "top1_cosine": hit.top1_cosine,
                        "top1_cluster_agreement": hit.top1_cluster_agreement,
                        "topk_majority": hit.topk_majority,
                        "escalation_reason": "pricing_basis_mismatch",
                        "logged_at": now,
                        "tier_a_pricing_basis": tier_a.pricing_basis,
                        "cluster_pricing_basis": hit.payload.get("pricing_basis"),
                    }
                )
            elif killswitched:
                tier_b_index.append_miss(
                    {
                        "cluster_id": hit.cluster_id,
                        "country": country,
                        "first_name": str(product.get("first_name") or ""),
                        "top1_cosine": hit.top1_cosine,
                        "top1_cluster_agreement": hit.top1_cluster_agreement,
                        "topk_majority": hit.topk_majority,
                        "escalation_reason": "killswitched",
                        "logged_at": now,
                    }
                )
            elif hit.accepted:
                source = dict(hit.payload)
                source["raw_response_text"] = ""
                source["total_tokens"] = 0
                source["model_version"] = f"tier_b/{config.EMBED_BACKEND}"
                source["cluster_agreement_coicop"] = hit.top1_cluster_agreement
                # Partial-accept (Phase 3): hit.payload has sub_label_id
                # already blanked by accept_from_picked, and the method label
                # below is greppable in match_log so a future async pass can
                # resolve sub_label_id via tier_c.enrich_sub_label_only()
                # when quota permits.
                method = f"tier_b_knn_{hit.escalation_reason}"
            elif hit.escalation_reason == "miss":
                tier_b_index.append_miss(
                    {
                        "cluster_id": hit.cluster_id,
                        "country": country,
                        "first_name": str(product.get("first_name") or ""),
                        "top1_cosine": hit.top1_cosine,
                        "top1_cluster_agreement": hit.top1_cluster_agreement,
                        "topk_majority": hit.topk_majority,
                        "escalation_reason": hit.escalation_reason,
                        "logged_at": now,
                    }
                )

        # Tier 3: embedding (skipped while MATCH_FUZZY_ENABLED=False)
        if source is None and config.MATCH_FUZZY_ENABLED:
            pass

        if source is not None and method is not None:
            cluster_agreement = float(source.get("cluster_agreement_coicop") or 0.0)
            payload = _overlay_tier_a(
                _payload_from_source(source), tier_a, cluster_agreement
            )
            # Phase-2 consolidation: arbitrate basis disagreements via
            # allowed_bases. Singleton-allowed leaves get the basis rewritten;
            # multi-allowed disagreements get tagged for tier-c arbitration.
            bucket, override_basis = cross_check.consolidate(
                payload.get("pricing_basis"),
                str(payload.get("coicop_code") or ""),
                payload.get("sub_label_id"),
            )
            if bucket == "SILENT_OVERRIDE" and override_basis:
                payload["pricing_basis"] = override_basis
                # Leaf-gate B-reset: see source-curated path above.
                payload["amount_value"] = None
                payload["standard_unit"] = cross_check.canonical_unit_for_basis(
                    override_basis
                )
            method_suffix = ""
            if bucket == "SILENT_OVERRIDE":
                method_suffix = "_basis_override"
            elif bucket == "ESCALATE_MULTI":
                method_suffix = "_basis_pending"
            raw_text = str(source.get("raw_response_text") or "")
            total_tokens = int(source.get("total_tokens") or 0)
            model_version = str(source.get("model_version") or config.MODEL_NAME)
            method_out = f"{method}{tier_a_suffix}{method_suffix}"
            for h in input_hashes:
                if h in hash_lookup:
                    continue
                cache_rows.append(
                    propagate_row(
                        h,
                        product,
                        payload,
                        method_out,
                        raw_text,
                        total_tokens,
                        model_version,
                        now,
                    )
                )
            match_log.append(
                {
                    "product_identity_key": str(pid) if isinstance(pid, str) else "",
                    "canonical_loose": str(loose) if isinstance(loose, str) else "",
                    "country": country,
                    "n_input_hashes": len(input_hashes),
                    "match_method": method_out,
                    "matched_at": now,
                }
            )
            cross_check_rows.append(
                cross_check.build_row(
                    row_id=str(pid) if isinstance(pid, str) else (str(loose) or ""),
                    country=country,
                    structural_basis=payload.get("pricing_basis"),
                    categorical_code=str(payload.get("coicop_code") or ""),
                    categorical_sub_label=payload.get("sub_label_id"),
                    matched_at=now,
                    consolidation_bucket=bucket,
                )
            )
        else:
            residual_idx.append(idx)

    residual = (
        products.loc[residual_idx].copy() if residual_idx else products.iloc[0:0].copy()
    )
    if not residual.empty:
        for f in _STRUCTURAL_FIELDS:
            residual[f"tier_a_{f}"] = [
                getattr(tier_a_by_idx[i], f) for i in residual.index
            ]
    return cache_rows, residual, match_log, cross_check_rows


def _append_match_log(rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    path = config.MATCH_LOG_PARQUET
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    if path.exists():
        existing = pd.read_parquet(path)
        out = pd.concat([existing, new], ignore_index=True)
    else:
        out = new
    out.to_parquet(path, index=False)


def run(products_parquet: Optional[Path] = None) -> None:
    products_parquet = products_parquet or config.PRODUCTS_PARQUET
    products = pd.read_parquet(products_parquet)
    cached = cache.read_cache()
    cache_rows, residual, match_log, cross_check_rows = cascade(products, cached)
    if cache_rows:
        cache.append_enrichments(cache_rows)
    _append_match_log(match_log)
    cross_check.append(cross_check_rows)
    asyncio.run(tier_c.run_residual(residual))
    pruned = cache.enforce_collision_invariant()
    if pruned:
        print(f"Pruned {pruned} cache_key(s) from _failed.parquet (now in enrichments)")
