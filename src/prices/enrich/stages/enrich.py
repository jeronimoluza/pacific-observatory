import asyncio
import json
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


def _load_coicop_context() -> str:
    subcats: dict[str, list[dict]] = {}
    if config.COICOP_SUBCATS_JSON.exists():
        subcats = json.loads(config.COICOP_SUBCATS_JSON.read_text())
    df = pd.read_excel(config.COICOP_XLSX)
    leaves = df[df["code"].astype(str).str.match(r"^\d{2}\.\d\.\d$", na=False)]
    lines: list[str] = []
    for r in leaves.itertuples():
        lines.append(f"{r.code} | {r.title}")
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


async def _enrich_async(df: pd.DataFrame) -> None:
    agent = _build_agent()
    already = cache.existing_keys()
    if not df.empty:
        df = df[~df.apply(lambda r: cache_key(_structured_input(r)) in already, axis=1)]
    sem = asyncio.Semaphore(config.CONCURRENCY)

    async def worker(chunk: pd.DataFrame) -> None:
        inputs = [_structured_input(r) for _, r in chunk.iterrows()]
        async with sem:
            result = await agent.run(json.dumps(inputs))
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

    chunks = [
        df.iloc[i : i + config.BATCH_SIZE] for i in range(0, len(df), config.BATCH_SIZE)
    ]
    if chunks:
        await asyncio.gather(*(worker(c) for c in chunks))


def run(input_parquet: Optional[Path] = None) -> None:
    input_parquet = input_parquet or config.PRODUCTS_INPUT_PARQUET
    df = pd.read_parquet(input_parquet)
    asyncio.run(_enrich_async(df))
