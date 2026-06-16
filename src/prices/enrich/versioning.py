import hashlib
import json
from pathlib import Path

from prices.enrich import config
from prices.enrich.schemas import EnrichmentBatch


def _sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes() if path.exists() else b""


# Manual prompt semver. Stamped onto each cached row as a provenance column.
# No longer part of the cache key — see cache_key() below.
# v1 → v2 (2026-06-09): multipack-math clarification, case-insensitive unit
# suffixes, mass-marker forces mass/volume basis. Selective re-enrich of
# cambodia/lager + malaysia/lip-balm buckets only (see drop_flagged_from_cache.py).
PROMPT_SEMVER = "v2"
PROMPT_BYTES_HASH = _sha12(_read_bytes(config.ENRICH_PROMPT_PATH))
TAXONOMY_PROMPT_VERSION = _sha12(_read_bytes(config.TAXONOMY_PROMPT_PATH))
SCHEMA_VERSION = _sha12(
    json.dumps(EnrichmentBatch.model_json_schema(), sort_keys=True).encode()
)
TAXONOMY_VERSION = _sha12(_read_bytes(config.COICOP_SUBCATS_JSON))


def canonical_json(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def input_hash(structured_input: dict) -> str:
    """Stable hash of the row's structured input. Identity-only — never includes
    prompt/schema/taxonomy versions."""
    return hashlib.sha256(canonical_json(structured_input).encode()).hexdigest()


def cache_key(structured_input: dict) -> str:
    """Cache lookup key. Decoupled from prompt: equals input_hash(structured_input).

    Prompt/schema/taxonomy version drift is recorded as provenance columns
    (`prompt_semver`, `schema_version`, `taxonomy_version`) on each cached row,
    not folded into the key. SCHEMA_VERSION drift is handled by partitioning the
    cache into one parquet per schema version (see cache.read_cache)."""
    return input_hash(structured_input)
