"""Observation deduplication via content hashing."""

import hashlib


def observation_hash(row: dict, key_fields: list[str]) -> str:
    """SHA-256 hash of key fields for dedup.

    Uses \\x00 as separator to prevent collisions from values containing
    common delimiters (pipes, commas, etc.).

    Args:
        row: dict-like row (or pd.Series accessed via .get())
        key_fields: list of field names to include in hash

    Returns:
        64-char hex digest
    """
    key = "\x00".join(str(row.get(f, "")) for f in key_fields)
    return hashlib.sha256(key.encode()).hexdigest()
