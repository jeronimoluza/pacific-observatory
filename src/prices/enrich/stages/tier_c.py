"""Tier (c) — KNN-aware LLM reranker.

The LLM is no longer a blind classifier. It receives the top-K nearest
cluster representatives from `tier_b` (with their resolved coicop / sub-
label and per-cluster agreement) and is asked to AUDIT the consensus
rather than re-solve from scratch. Adversarial framing pushes it to flip
the consensus only when it can defend the flip.

Pipeline per residual product:
    1. Look up top-K KNN neighbors (re-uses the tier-b index; embed cache
       makes the second call free).
    2. Build a `user_payload` with the product + neighbors + tier-a
       structural hints.
    3. Call `LLM_MODEL_BASELINE` (flash-lite) with temperature=0.
    4. Validate the returned `coicop_code` against the taxonomy. On miss,
       single-product retry with "closest valid: X, Y" feedback. Second
       failure → `state='requires_review'`.
    5. If `confidence < LLM_CONFIDENCE_THRESHOLD` OR the response
       disagrees with a unanimous KNN consensus, escalate to
       `LLM_MODEL_ESCALATE` (pro). Pro response replaces flash-lite. If
       pro holds in disagreement → `state='resolved_with_low_neighbor_agreement'`.

`L1_CACHE` is an in-process dict keyed by product_identity_key for
intra-run repeated hits.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import pandas as pd
import yaml
from pydantic_ai import Agent

from prices.enrich import cache, config, rate_limit
from prices.enrich import index as tier_b_index
from prices.enrich.propagation import product_input_hashes, propagate_row
from prices.enrich.schemas import EnrichmentBatch, ProductEnrichment
from prices.enrich.scope import build_scope_constrained, build_scope_residual
from prices.enrich.taxonomy_index import (
    closest_codes as _closest_codes,
    load_coicop_context as _load_coicop_context,
    load_taxonomy_index as _load_taxonomy_index,
)
from prices.enrich.versioning import cache_key, input_hash


_CHANNEL_PRIORS_CACHE: Optional[dict[str, list[str]]] = None


def _channel_priors() -> dict[str, list[str]]:
    global _CHANNEL_PRIORS_CACHE
    if _CHANNEL_PRIORS_CACHE is None:
        try:
            with open(config.CHANNEL_COICOP_PRIORS_PATH, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except FileNotFoundError:
            raw = {}
        _CHANNEL_PRIORS_CACHE = {
            str(k): [str(v) for v in (val or [])] for k, val in raw.items()
        }
    return _CHANNEL_PRIORS_CACHE


def _priors_for(channel: Optional[str]) -> list[str]:
    if not channel:
        return []
    return _channel_priors().get(channel, [])


def _append_channel_outlier(row: dict) -> None:
    p = config.CHANNEL_OUTLIERS_PARQUET
    p.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame([row])
    if p.exists():
        out = pd.concat([pd.read_parquet(p), new], ignore_index=True)
    else:
        out = new
    out.to_parquet(p, index=False)


_RETRY_AFTER_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s")
_RATE_LIMIT_MAX_ATTEMPTS = 6
_RATE_LIMIT_DEFAULT_DELAY = 20.0
_RATE_LIMIT_CAP_DELAY = 60.0


L1_CACHE: dict[str, dict] = {}


def _build_baseline_agent(
    model_id: str,
    scope: Optional[frozenset] = None,
) -> Agent:
    """Build a baseline tier-c Agent with the COICOP block substituted at the
    `{coicop_context}` placeholder.

    `scope=None` → full 538-leaf block (legacy behavior). `scope=frozenset`
    → only the named leaves rendered in that slot. Per-scope construction
    is the right way to swap context: pydantic-ai's `instructions=` lands
    as a SEPARATE message from `system_prompt`, and Gemini treats the two
    with different authority — a smoke replay showed 70% baseline agreement
    when scope was sent via `instructions=` (model over-picked `_other`).
    Substituting in the original slot restores the leaf vocabulary's
    in-prompt position and recovers parity."""
    prompt_template = config.ENRICH_PROMPT_PATH.read_text()
    coicop_block = _load_coicop_context(scope)
    system_prompt = prompt_template.replace("{coicop_context}", coicop_block)
    # Adversarial KNN framing appended to the existing system prompt.
    system_prompt += (
        "\n\n## KNN consensus framing (tier-c)\n"
        "Each product comes with up to K nearest neighbors from our enrichments\n"
        "database, each carrying a resolved `coicop_code`, `sub_label_id` and\n"
        "`agreement` (0..1 vote concentration in the source cluster). YOUR JOB\n"
        "IS TO AUDIT the consensus, not re-solve from scratch. Default to the\n"
        "majority coicop_code+sub_label_id when neighbors agree and the product\n"
        "fits the pattern. FLIP only if you can articulate why the consensus is\n"
        "wrong for this specific product. When you flip, `confidence` should\n"
        "reflect how strongly you can defend the flip — low confidence means\n"
        "you're guessing.\n"
        "If tier_a_* fields are present (pricing_basis, amount_value, etc.),\n"
        "treat them as deterministic regex output — don't override them, your\n"
        "structural fields will be ignored by the downstream overlay."
        "\n\n## Channel prior (tier-c)\n"
        "If `channel_coicop_priors` is non-empty in the payload, the row comes\n"
        "from a retailer whose catalog typically covers those COICOP top-levels.\n"
        "PREFER coicop_codes whose top-level (first two digits) is in that list.\n"
        "Only choose a code outside the list when the product description\n"
        "clearly identifies a category the channel doesn't normally sell —\n"
        "pharmacy candy, supermarket pet food, fuel-station snacks are all\n"
        "legitimate outliers. The list is a soft prior, not a hard restriction."
    )
    try:
        return Agent(
            f"google-gla:{model_id}",
            output_type=EnrichmentBatch,
            system_prompt=system_prompt,
            output_retries=config.OUTPUT_RETRIES,
            model_settings={"temperature": config.LLM_TEMPERATURE},
        )
    except TypeError:
        # Older pydantic_ai signatures without model_settings — fall back.
        return Agent(
            f"google-gla:{model_id}",
            output_type=EnrichmentBatch,
            system_prompt=system_prompt,
            output_retries=config.OUTPUT_RETRIES,
        )


def _neighbors_for(country: str, query_text: str, k: int) -> list[dict]:
    """Return up to k cluster-rep neighbors for the given query text. Empty
    list when no country index exists (bootstrap / pre-build / unknown country)."""
    loaded = tier_b_index._get_index(country)
    if loaded is None:
        return []
    idx, clusters = loaded
    if len(clusters) == 0:
        return []
    from prices.enrich.embed import embed_texts

    vec = embed_texts(
        [f"query: {query_text}"],
        backend=config.EMBED_BACKEND,
        dim=config.EMBED_DIM,
    )
    k_eff = min(k, len(clusters))
    labels, dists = idx.knn_query(vec, k=k_eff)
    out: list[dict] = []
    for lab, dist in zip(labels[0], dists[0]):
        row = clusters.iloc[int(lab)]
        out.append(
            {
                "name": str(row.get("representative_name") or ""),
                "coicop_code": row.get("coicop_code"),
                "sub_label_id": row.get("sub_label_id"),
                "agreement": float(row.get("cluster_agreement_coicop") or 0.0),
                "cosine": float(1.0 - dist),
            }
        )
    return out


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


def _product_input(row, neighbors: list[dict]) -> dict:
    """LLM-payload shape for one residual product, including KNN neighbors
    and any tier-a structural hints that fired."""
    channel = str(row.get("channel") or "") if not pd.isna(row.get("channel")) else ""
    payload = {
        "product_name_original": str(row["first_name"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
        "neighbors": neighbors,
    }
    if channel:
        payload["channel"] = channel
        priors = _priors_for(channel)
        if priors:
            payload["channel_coicop_priors"] = priors
    for f in _STRUCTURAL_FIELDS:
        col = f"tier_a_{f}"
        if col in row.index:
            val = row.get(col)
            # pandas dtype-aware "missing" check.
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                payload[f"tier_a_{f}"] = val
    return payload


def _unanimous_neighbor_code(neighbors: list[dict]) -> Optional[str]:
    if not neighbors:
        return None
    codes = [n.get("coicop_code") for n in neighbors if n.get("coicop_code")]
    if len(codes) < 3:
        return None
    if all(c == codes[0] for c in codes):
        return codes[0]
    return None


def _payload_from_enrichment(p: ProductEnrichment) -> dict:
    return {
        "pricing_basis": p.pricing_basis,
        "amount_value": p.amount_value,
        "standard_unit": p.standard_unit,
        "count": p.count,
        "multiplier": p.multiplier,
        "dimensions_json": json.dumps([d.model_dump() for d in p.dimensions]),
        "coicop_code": p.coicop_code,
        "sub_label_id": p.sub_label_id,
        "is_promotion": p.flags.is_promotion,
        "is_bundle": p.flags.is_bundle,
        "is_multipack": p.flags.is_multipack,
        "promo_reason": p.flags.promo_reason,
        "confidence": p.confidence,
        "state": p.state,
    }


def _llm_flatten(
    products_chunk: pd.DataFrame,
    enrichments: list[ProductEnrichment],
    raw_text: str,
    total_tokens: int,
    method: str,
    model_version: str,
) -> list[dict]:
    rows: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for (_, product), p in zip(products_chunk.iterrows(), enrichments):
        payload = _payload_from_enrichment(p)
        for h in product_input_hashes(product):
            rows.append(
                propagate_row(
                    h,
                    product,
                    payload,
                    method,
                    raw_text,
                    total_tokens,
                    model_version,
                    now,
                )
            )
    return rows


def _agent_model(agent: Agent) -> str:
    m = getattr(agent, "model", None)
    name = getattr(m, "model_name", None) or getattr(m, "name", None) or str(m or "")
    # `model_name` is bare ("gemini-3.1-flash-lite"); prefixed model strings
    # ("google-gla:gemini-...") drop the prefix here.
    return name.split(":")[-1] if name else config.LLM_MODEL_BASELINE


@lru_cache(maxsize=256)
def _scoped_agent(model_id: str, scope: Optional[frozenset]) -> Agent:
    """LRU-cached factory for scope-specific Agents. Cache size 256 covers
    realistic scope diversity in a run; scope=None (full taxonomy) is one
    of the cached entries."""
    return _build_baseline_agent(model_id, scope=scope)


async def _run_with_retry_after(
    agent: Agent,
    payload: str,
    scope: Optional[frozenset] = None,
):
    """Proactive RPM/TPM/RPD throttle + reactive 429 backoff. Acquire blocks
    until the bucket has headroom; rate_limit.DailyQuotaExhausted propagates
    so the caller halts cleanly rather than burning retries. The bucket's
    last token estimate is replaced with the response's actual usage so TPM
    accounting stays honest.

    `scope` selects an LRU-cached Agent whose system_prompt has the scoped
    COICOP block substituted at the original `{coicop_context}` slot.
    `scope=None` keeps the passed-in `agent` (legacy full-taxonomy path)."""
    model = _agent_model(agent)
    if scope is not None:
        agent = _scoped_agent(model, scope)
    estimate = max(
        config.RATE_LIMIT_TOKEN_ESTIMATE_PER_CALL,
        len(payload) // 3 + 2_000,
    )
    for _ in range(_RATE_LIMIT_MAX_ATTEMPTS):
        await rate_limit.acquire(model, estimated_tokens=estimate)
        try:
            result = await agent.run(payload)
        except Exception as e:
            s = str(e)
            if "429" not in s and "RESOURCE_EXHAUSTED" not in s:
                raise
            m = _RETRY_AFTER_RE.search(s)
            delay = float(m.group(1)) if m else _RATE_LIMIT_DEFAULT_DELAY
            delay = min(delay + 1.0, _RATE_LIMIT_CAP_DELAY)
            await asyncio.sleep(delay)
            continue
        usage_fn = getattr(result, "usage", None)
        tokens_obj = usage_fn() if callable(usage_fn) else None
        actual = getattr(tokens_obj, "total_tokens", 0) if tokens_obj else 0
        if actual:
            rate_limit.record_actual(model, int(actual))
        return result
    raise RuntimeError(
        f"Rate-limit retry budget exhausted ({_RATE_LIMIT_MAX_ATTEMPTS})"
    )


async def _single_enrich(
    agent: Agent,
    product,
    payload: dict,
    scope: Optional[frozenset] = None,
) -> Optional[ProductEnrichment]:
    """One-product LLM call (used for retry + escalation paths)."""
    result = await _run_with_retry_after(agent, json.dumps([payload]), scope=scope)
    products = result.output.products
    if not products:
        return None
    return products[0]


async def _validate_and_retry(
    agent: Agent,
    product,
    payload: dict,
    enrichment: ProductEnrichment,
    scope: Optional[frozenset] = None,
) -> tuple[ProductEnrichment, bool]:
    """Validate enrichment against taxonomy. If `coicop_code` is invalid,
    single-product retry with closest-valid-codes feedback. Returns
    (final_enrichment, requires_review_flag).

    The retry widens `scope` to include the closest-valid codes so the model
    can actually see their definitions in the per-run instructions."""
    leaves, sub_index = _load_taxonomy_index()
    if enrichment.coicop_code in leaves:
        return enrichment, False
    closest = _closest_codes(enrichment.coicop_code, leaves)
    retry_payload = dict(payload)
    retry_payload["_taxonomy_feedback"] = {
        "invalid_code": enrichment.coicop_code,
        "closest_valid": closest,
        "note": "previous attempt returned a code not in the COICOP taxonomy",
    }
    retry_scope = frozenset(set(scope) | set(closest)) if scope is not None else None
    try:
        retry = await _single_enrich(agent, product, retry_payload, scope=retry_scope)
    except Exception:
        retry = None
    if retry is not None and retry.coicop_code in leaves:
        return retry, False
    if retry is None:
        retry = enrichment
    return retry, True


async def _maybe_escalate(
    escalate_agent: Optional[Agent],
    product,
    payload: dict,
    neighbors: list[dict],
    enrichment: ProductEnrichment,
    scope: Optional[frozenset] = None,
) -> tuple[ProductEnrichment, str, str]:
    """Apply confidence-escalation + KNN-disagreement protocol. Returns
    (final_enrichment, method_suffix, model_version)."""
    if escalate_agent is None:
        return enrichment, "tier_c_llm", config.LLM_MODEL_BASELINE
    low_conf = enrichment.confidence < config.LLM_CONFIDENCE_THRESHOLD
    consensus = _unanimous_neighbor_code(neighbors)
    disagree = consensus is not None and enrichment.coicop_code != consensus
    if not (low_conf or disagree):
        return enrichment, "tier_c_llm", config.LLM_MODEL_BASELINE
    adversarial_payload = dict(payload)
    if disagree:
        adversarial_payload["_disagreement"] = {
            "neighbor_consensus_code": consensus,
            "flash_lite_chose": enrichment.coicop_code,
            "instruction": "neighbors voted X, flash-lite voted Y — defend or flip",
        }
    try:
        pro = await _single_enrich(
            escalate_agent,
            product,
            adversarial_payload,
            scope=scope,
        )
    except Exception:
        return enrichment, "tier_c_llm", config.LLM_MODEL_BASELINE
    if pro is None:
        return enrichment, "tier_c_llm", config.LLM_MODEL_BASELINE
    if disagree and pro.coicop_code == enrichment.coicop_code:
        # Pro held the disagreeing answer — mark resolution as low-neighbor-agreement.
        pro = pro.model_copy(update={"state": "resolved_with_low_neighbor_agreement"})
    return pro, "tier_c_llm_escalated", config.LLM_MODEL_ESCALATE


async def _process_chunk(
    chunk: pd.DataFrame,
    payloads: list[dict],
    neighbors_per_row: list[list[dict]],
    baseline_agent: Agent,
    escalate_agent: Optional[Agent],
    scope: Optional[frozenset] = None,
) -> list[dict]:
    """Run one batch through baseline → validate/retry → maybe-escalate.
    Returns cache rows ready for append.

    `scope` is the chunk-wide COICOP leaf set rendered into per-call
    instructions. Per-product retry/escalation reuses the same scope (the
    chunk-wide union already covers each row's neighbor codes)."""
    try:
        batch_result = await _run_with_retry_after(
            baseline_agent,
            json.dumps(payloads),
            scope=scope,
        )
    except Exception as batch_err:
        # Per-product fallback if the batch fails wholesale.
        rows: list[dict] = []
        for (_, product), pld, nbrs in zip(
            chunk.iterrows(), payloads, neighbors_per_row
        ):
            r = await _single_product_pipeline(
                product,
                pld,
                nbrs,
                baseline_agent,
                escalate_agent,
                batch_err,
                scope=scope,
            )
            rows.extend(r)
        return rows

    enrichments = batch_result.output.products
    if len(enrichments) != len(payloads):
        raise RuntimeError(
            f"Length mismatch: {len(payloads)} in, {len(enrichments)} out"
        )

    raw_text = str(getattr(batch_result, "all_messages", lambda: "")())[:8000]
    usage_fn = getattr(batch_result, "usage", None)
    tokens_obj = usage_fn() if callable(usage_fn) else None
    total_tokens = getattr(tokens_obj, "total_tokens", 0) if tokens_obj else 0

    rows: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for (_, product), pld, nbrs, p in zip(
        chunk.iterrows(), payloads, neighbors_per_row, enrichments
    ):
        try:
            validated, requires_review = await _validate_and_retry(
                baseline_agent,
                product,
                pld,
                p,
                scope=scope,
            )
        except Exception:
            validated, requires_review = p, False
        if requires_review:
            validated = validated.model_copy(update={"state": "requires_review"})
            method, model_version = (
                "tier_c_llm_requires_review",
                config.LLM_MODEL_BASELINE,
            )
        else:
            validated, method, model_version = await _maybe_escalate(
                escalate_agent,
                product,
                pld,
                nbrs,
                validated,
                scope=scope,
            )
        _log_channel_outlier_if_needed(product, pld, validated)
        payload_out = _payload_from_enrichment(validated)
        pid = product.get("product_identity_key")
        if isinstance(pid, str) and pid:
            L1_CACHE[pid] = payload_out
        for h in product_input_hashes(product):
            rows.append(
                propagate_row(
                    h,
                    product,
                    payload_out,
                    method,
                    raw_text,
                    total_tokens,
                    model_version,
                    now,
                )
            )
    return rows


def _log_channel_outlier_if_needed(product, payload: dict, enrichment) -> None:
    """Append a row to _channel_outliers.parquet when the LLM picked a COICOP
    top-level outside the channel's prior list. Telemetry only — does not
    affect the enrichment outcome."""
    if not getattr(config, "CHANNEL_OUTLIER_AUDIT", True):
        return
    priors = payload.get("channel_coicop_priors") or []
    if not priors:
        return
    code = getattr(enrichment, "coicop_code", "") or ""
    if not code or len(code) < 2:
        return
    accepted_top = code[:2]
    if accepted_top in priors:
        return
    _append_channel_outlier(
        {
            "input_hash": input_hash(payload),
            "product_name_original": str(product.get("first_name") or ""),
            "country": str(product.get("country") or ""),
            "channel": payload.get("channel"),
            "expected_top_levels": priors,
            "accepted_top_level": accepted_top,
            "accepted_code": code,
            "confidence": float(getattr(enrichment, "confidence", 0.0) or 0.0),
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
    )


async def _single_product_pipeline(
    product,
    payload: dict,
    neighbors: list[dict],
    baseline_agent: Agent,
    escalate_agent: Optional[Agent],
    batch_err: Exception,
    scope: Optional[frozenset] = None,
) -> list[dict]:
    """Per-product fallback path used when the batch call fails."""
    last_err: Exception | None = batch_err
    for _ in range(config.OUTPUT_RETRIES):
        try:
            p = await _single_enrich(baseline_agent, product, payload, scope=scope)
            if p is None:
                continue
            validated, requires_review = await _validate_and_retry(
                baseline_agent,
                product,
                payload,
                p,
                scope=scope,
            )
            if requires_review:
                validated = validated.model_copy(update={"state": "requires_review"})
                method, model_version = (
                    "tier_c_llm_requires_review",
                    config.LLM_MODEL_BASELINE,
                )
            else:
                validated, method, model_version = await _maybe_escalate(
                    escalate_agent,
                    product,
                    payload,
                    neighbors,
                    validated,
                    scope=scope,
                )
            payload_out = _payload_from_enrichment(validated)
            pid = product.get("product_identity_key")
            if isinstance(pid, str) and pid:
                L1_CACHE[pid] = payload_out
            now = datetime.now(timezone.utc).isoformat()
            return [
                propagate_row(
                    h,
                    product,
                    payload_out,
                    method,
                    "",
                    0,
                    model_version,
                    now,
                )
                for h in product_input_hashes(product)
            ]
        except Exception as e:
            last_err = e
            continue
    cache.append_failures(
        [
            {
                "cache_key": cache_key(payload),
                "input_hash": input_hash(payload),
                "product_identity_key": product.get("product_identity_key"),
                "product_name_original": str(product.get("first_name") or ""),
                "country": str(product.get("country") or ""),
                "last_error": f"batch_err={batch_err}; last={last_err}",
                "attempt_count": config.OUTPUT_RETRIES,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    return []


async def enrich_sub_label_only(
    product,
    accepted_coicop_code: str,
    neighbors: list[dict],
    baseline_agent: Optional[Agent] = None,
) -> Optional[str]:
    """Constrained tier-c — sub_label_id only.

    Used when tier-b accepted the coicop_code but the K same-coicop neighbors
    disagreed on sub_label_id below ``KNN_SUB_LABEL_AGREEMENT_MIN``. Reuses
    the baseline-agent system prompt (so includes/excludes + KNN consensus
    framing carry through) and adds a constraint that pins the coicop and
    restricts the choice to the leaf's valid sub-vocabulary.

    Returns the chosen sub_label_id (always a member of the valid set,
    including ``_other``), or None when the call fails.
    """
    agent = baseline_agent or _build_baseline_agent(config.LLM_MODEL_BASELINE)
    leaves, sub_index = _load_taxonomy_index()
    valid = sorted(sub_index.get(accepted_coicop_code, {"_other"}))
    payload = _product_input(product, neighbors)
    payload["_sub_label_only"] = {
        "instruction": (
            "Tier-b already locked the COICOP. Pick sub_label_id ONLY from "
            "`valid_sub_labels` for the LOCKED coicop_code. Other fields in "
            "your response are ignored — only sub_label_id matters."
        ),
        "locked_coicop_code": accepted_coicop_code,
        "valid_sub_labels": valid,
    }
    scope = build_scope_constrained(accepted_coicop_code)
    try:
        result = await _single_enrich(agent, product, payload, scope=scope)
    except Exception:
        return None
    if result is None:
        return None
    if result.sub_label_id in valid:
        return result.sub_label_id
    return "_other"


async def run_residual(residual: pd.DataFrame) -> None:
    """Async entry: run the KNN-aware LLM tier over a residual DataFrame and
    persist rows to the cache."""
    if residual.empty:
        return
    baseline_agent = _build_baseline_agent(config.LLM_MODEL_BASELINE)
    escalate_agent = None
    if (
        config.LLM_MODEL_ESCALATE
        and config.LLM_MODEL_ESCALATE != config.LLM_MODEL_BASELINE
    ):
        escalate_agent = _build_baseline_agent(config.LLM_MODEL_ESCALATE)
    sem = asyncio.Semaphore(config.CONCURRENCY)
    leaves, _sub_index = _load_taxonomy_index()

    async def worker(chunk: pd.DataFrame) -> None:
        nbrs_per_row: list[list[dict]] = []
        payloads: list[dict] = []
        cache_hits: list[Optional[dict]] = []
        for _, row in chunk.iterrows():
            pid = row.get("product_identity_key")
            if isinstance(pid, str) and pid and pid in L1_CACHE:
                cache_hits.append(L1_CACHE[pid])
                nbrs_per_row.append([])
                payloads.append({})
                continue
            cache_hits.append(None)
            country = str(row.get("country") or "")
            name = str(row.get("first_name") or "")
            nbrs = _neighbors_for(country, name, config.KNN_K)
            nbrs_per_row.append(nbrs)
            payloads.append(_product_input(row, nbrs))

        # Flatten L1 hits directly without an LLM call.
        rows: list[dict] = []
        now = datetime.now(timezone.utc).isoformat()
        for (_, product), hit in zip(chunk.iterrows(), cache_hits):
            if hit is None:
                continue
            for h in product_input_hashes(product):
                rows.append(
                    propagate_row(
                        h,
                        product,
                        hit,
                        "tier_c_llm_l1_hit",
                        "",
                        0,
                        config.LLM_MODEL_BASELINE,
                        now,
                    )
                )

        residual_mask = [hit is None for hit in cache_hits]
        residual_chunk = chunk[residual_mask] if not all(residual_mask) else chunk
        residual_payloads = [p for p, m in zip(payloads, residual_mask) if m]
        residual_nbrs = [n for n, m in zip(nbrs_per_row, residual_mask) if m]

        if not residual_chunk.empty:
            # Chunk-wide scope = union(neighbor codes) ∪ COICOP-3 siblings.
            # Empty union → scope=None (full taxonomy fallback) so a no-signal
            # batch never gets context-starved.
            nbr_codes = [n.get("coicop_code") for nbrs in residual_nbrs for n in nbrs]
            scope = build_scope_residual(nbr_codes, leaves)
            scope_arg: Optional[frozenset] = scope if scope else None
            async with sem:
                rows.extend(
                    await _process_chunk(
                        residual_chunk,
                        residual_payloads,
                        residual_nbrs,
                        baseline_agent,
                        escalate_agent,
                        scope=scope_arg,
                    )
                )
        if rows:
            cache.append_enrichments(rows)

    chunks = [
        residual.iloc[i : i + config.BATCH_SIZE]
        for i in range(0, len(residual), config.BATCH_SIZE)
    ]
    if chunks:
        await asyncio.gather(*(worker(c) for c in chunks))
