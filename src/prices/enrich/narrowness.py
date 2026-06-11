"""Narrowness rule and resolved-code helpers for the source-curated short-circuit.

See ADR-0002. A source's declared `coicop_codes` is narrow iff all codes share
a single 3-digit class prefix (e.g. ["04.1.1"] or ["04.1.1", "04.1.2"]). Narrow
sources bypass tier-b and tier-c; tier-a still runs for structural overlay.
"""

from __future__ import annotations


_CODES_SEPARATOR = "|"


def parse_codes(serialized: str | None) -> list[str]:
    """Parse the `|`-joined per-row representation back into a code list."""
    if not isinstance(serialized, str) or not serialized:
        return []
    return [c for c in serialized.split(_CODES_SEPARATOR) if c]


def serialize_codes(codes: list[str] | None) -> str:
    if not codes:
        return ""
    return _CODES_SEPARATOR.join(sorted({c for c in codes if c}))


def is_narrow(codes: list[str]) -> bool:
    """γ: True iff every code shares a single 3-digit class prefix."""
    if not codes:
        return False
    prefixes = {c[:4] for c in codes if isinstance(c, str) and len(c) >= 4}
    return len(prefixes) == 1


def resolved_code(codes: list[str]) -> str:
    """Most-specific shared code per ADR-0002.

    Single 4-digit code declared → that code. Multiple codes sharing one
    3-digit class → the 3-digit class prefix. Caller must ensure `is_narrow`.
    """
    unique = sorted({c for c in codes if isinstance(c, str) and c})
    if len(unique) == 1:
        return unique[0]
    return unique[0][:4]
