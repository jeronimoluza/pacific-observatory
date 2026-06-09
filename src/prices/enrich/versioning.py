import hashlib
import json
from pathlib import Path

from prices.enrich import config
from prices.enrich.schemas import EnrichmentBatch


def _sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


# Manual prompt semver. Bump explicitly when a prompt change should
# invalidate the cache and trigger re-enrichment. Auto-hashing the prompt
# file would force a full 41k-row re-enrichment on every typo fix, which
# burns >80 days of free-tier RPD; the semver gives us control.
# v1 → v2 (2026-06-09): multipack-math clarification, case-insensitive unit
# suffixes, mass-marker forces mass/volume basis. Selective re-enrich of
# cambodia/lager + malaysia/lip-balm buckets only (see drop_flagged_from_cache.py).
PROMPT_SEMVER = "v2"
# Audit-only: stamped on each cache row to detect silent drift within a
# semver (someone edited the prompt but forgot to bump). Not in cache_key.
PROMPT_BYTES_HASH = _sha12(_read_bytes(config.ENRICH_PROMPT_PATH))
TAXONOMY_PROMPT_VERSION = _sha12(_read_bytes(config.TAXONOMY_PROMPT_PATH))
SCHEMA_VERSION = _sha12(
    json.dumps(EnrichmentBatch.model_json_schema(), sort_keys=True).encode()
)
TAXONOMY_VERSION = _sha12(_read_bytes(config.COICOP_SUBCATS_JSON))


def canonical_json(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def input_hash(structured_input: dict) -> str:
    """Stable hash for prepare-stage dedup (does NOT include version hashes)."""
    return hashlib.sha256(canonical_json(structured_input).encode()).hexdigest()


def cache_key(structured_input: dict) -> str:
    """Cache key for enrich stage; invalidates on manual PROMPT_SEMVER bump."""
    payload = (
        canonical_json(structured_input)
        + PROMPT_SEMVER
        + SCHEMA_VERSION
        + TAXONOMY_VERSION
    )
    return hashlib.sha256(payload.encode()).hexdigest()
