"""Cache-row propagation helpers shared by the cascade and the LLM tier.

Lives outside `stages/enrich.py` so `stages/tier_c.py` can reuse the same
row-shape without a circular import.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.versioning import (
    PROMPT_BYTES_HASH,
    PROMPT_SEMVER,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
)


def product_input_hashes(product) -> list[str]:
    raw = product.get("input_hashes")
    if raw is None:
        return []
    return [h for h in raw if isinstance(h, str) and h]


def propagate_row(
    input_h: str,
    product,
    payload: dict,
    method: str,
    raw_text: str,
    total_tokens: int,
    model_version: str,
    now: str,
) -> dict:
    return {
        "cache_key": input_h,
        "input_hash": input_h,
        "match_method": method,
        "modality": "retail",
        "product_identity_key": product["product_identity_key"],
        "canonical_loose": product["canonical_loose"],
        "product_name_original": str(product["first_name"]),
        "category": ""
        if pd.isna(product.get("category"))
        else str(product["category"]),
        "country": str(product["country"]),
        "currency": str(product["currency"]),
        **payload,
        "raw_response_text": raw_text,
        "total_tokens": total_tokens,
        "model_version": model_version,
        "prompt_semver": PROMPT_SEMVER,
        "prompt_bytes_hash": PROMPT_BYTES_HASH,
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "trust_level": "high",
        "created_at": now,
    }
