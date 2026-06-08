import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic_ai import Agent

from prices.enrich import cache, config
from prices.enrich.schemas import EnrichmentBatch, ProductEnrichment
from prices.enrich.versioning import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
    cache_key,
)

_RETRY_AFTER_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s")
_RATE_LIMIT_MAX_ATTEMPTS = 6
_RATE_LIMIT_DEFAULT_DELAY = 20.0
_RATE_LIMIT_CAP_DELAY = 60.0


def _load_coicop_context() -> str:
    subcats: dict[str, list[dict]] = {}
    if config.COICOP_SUBCATS_JSON.exists():
        subcats = json.loads(config.COICOP_SUBCATS_JSON.read_text())
    df = pd.read_excel(config.COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    codes = set(df["code"])
    df = df[
        df["code"].apply(
            lambda c: not any(
                other != c and other.startswith(c + ".") for other in codes
            )
        )
    ]
    lines: list[str] = []
    for r in df.itertuples():
        title = str(r.title).replace("_x000D_", "").strip()
        lines.append(f"{r.code} | {title}")
        for entry in subcats.get(r.code, []):
            syns = ", ".join(entry.get("synonyms", [])[:4])
            lines.append(f"  - {entry['id']} | {entry['label']} | synonyms: {syns}")
    return "\n".join(lines)


def _structured_input(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def _build_agent() -> Agent:
    prompt_template = config.ENRICH_PROMPT_PATH.read_text()
    system_prompt = prompt_template.replace("{coicop_context}", _load_coicop_context())
    # pydantic-ai 1.41: string-form model spec resolves the provider via the
    # `google-gla:` prefix (Google Generative Language API).
    return Agent(
        f"google-gla:{config.MODEL_NAME}",
        output_type=EnrichmentBatch,
        system_prompt=system_prompt,
        output_retries=config.OUTPUT_RETRIES,
    )


def _flatten_for_cache(
    inputs: list[dict],
    products: list[ProductEnrichment],
    raw_text: str,
    total_tokens: int,
) -> list[dict]:
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for inp, p in zip(inputs, products):
        rows.append(
            {
                "cache_key": cache_key(inp),
                **inp,
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
                "raw_response_text": raw_text,
                "total_tokens": total_tokens,
                "model_version": config.MODEL_NAME,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "taxonomy_version": TAXONOMY_VERSION,
                "created_at": now,
            }
        )
    return rows


async def _run_with_retry_after(agent: Agent, payload: str):
    """Call agent.run; on 429 RESOURCE_EXHAUSTED, honor server's retryDelay and re-try.

    Why: free-tier Gemini returns `Please retry in Xs` on TPM exhaustion. The
    default code immediately re-tries and is throttled again, burning attempts
    for nothing. Sleeping until the TPM window refills is the correct fix.
    """
    for _ in range(_RATE_LIMIT_MAX_ATTEMPTS):
        try:
            return await agent.run(payload)
        except Exception as e:
            s = str(e)
            if "429" not in s and "RESOURCE_EXHAUSTED" not in s:
                raise
            m = _RETRY_AFTER_RE.search(s)
            delay = float(m.group(1)) if m else _RATE_LIMIT_DEFAULT_DELAY
            delay = min(delay + 1.0, _RATE_LIMIT_CAP_DELAY)
            await asyncio.sleep(delay)
    raise RuntimeError(
        f"Rate-limit retry budget exhausted ({_RATE_LIMIT_MAX_ATTEMPTS})"
    )


async def _enrich_async(df: pd.DataFrame) -> None:
    agent = _build_agent()
    already = cache.existing_keys()
    if not df.empty:
        df = df[~df.apply(lambda r: cache_key(_structured_input(r)) in already, axis=1)]
    sem = asyncio.Semaphore(config.CONCURRENCY)

    async def worker(chunk: pd.DataFrame) -> None:
        inputs = [_structured_input(r) for _, r in chunk.iterrows()]
        async with sem:
            try:
                result = await _run_with_retry_after(agent, json.dumps(inputs))
                products = result.output.products
                if len(products) != len(inputs):
                    raise RuntimeError(
                        f"Length mismatch: {len(inputs)} in, {len(products)} out"
                    )
                raw_text = str(getattr(result, "all_messages", lambda: "")())[:8000]
                usage_fn = getattr(result, "usage", None)
                tokens = usage_fn() if callable(usage_fn) else None
                total_tokens = getattr(tokens, "total_tokens", 0) if tokens else 0
                rows = _flatten_for_cache(inputs, products, raw_text, total_tokens)
                cache.append_enrichments(rows)
            except Exception as batch_err:
                for inp in inputs:
                    await _enrich_single(agent, inp, batch_err)

    chunks = [
        df.iloc[i : i + config.BATCH_SIZE] for i in range(0, len(df), config.BATCH_SIZE)
    ]
    if chunks:
        await asyncio.gather(*(worker(c) for c in chunks))


async def _enrich_single(agent: Agent, inp: dict, batch_err: Exception) -> None:
    last_err: Exception | None = batch_err
    for _ in range(config.OUTPUT_RETRIES):
        try:
            result = await _run_with_retry_after(agent, json.dumps([inp]))
            products = result.output.products
            if products:
                raw = str(getattr(result, "all_messages", lambda: "")())[:8000]
                usage_fn = getattr(result, "usage", None)
                tokens = usage_fn() if callable(usage_fn) else None
                ttok = getattr(tokens, "total_tokens", 0) if tokens else 0
                rows = _flatten_for_cache([inp], products, raw, ttok)
                cache.append_enrichments(rows)
                return
        except Exception as e:
            last_err = e
            continue
    cache.append_failures(
        [
            {
                "cache_key": cache_key(inp),
                **inp,
                "last_error": f"batch_err={batch_err}; last={last_err}",
                "attempt_count": config.OUTPUT_RETRIES,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )


def run(input_parquet: Optional[Path] = None) -> None:
    input_parquet = input_parquet or config.PRODUCTS_INPUT_PARQUET
    df = pd.read_parquet(input_parquet)
    asyncio.run(_enrich_async(df))
    pruned = cache.enforce_collision_invariant()
    if pruned:
        print(f"Pruned {pruned} cache_key(s) from _failed.parquet (now in enrichments)")
