"""Narrowness rule and resolved-code helpers for the source-curated short-circuit.

See ADR-0002. A source's declared `coicop_codes` is narrow iff (1) all codes
share a single 3-digit class prefix (e.g. ["04.1.1"] or ["04.1.1", "04.1.2"])
AND (2) the code that prefix resolves to (`resolved_code`) is an actual
taxonomy leaf -- a node with no children. Condition (1) alone used to be the
whole rule; it let a source short-circuit to a PARENT node (e.g. "02.1"
Alcoholic beverages, which has children 02.1.1/02.1.2/02.1.3) and stamp every
product under it with confidence=1.0. Narrow sources bypass the classifier;
structural extraction still runs for overlay.

This module stays pure logic with no I/O: `is_narrow` takes the caller's
already-loaded leaf set (`prices.enrich.coicop_taxonomy.load_taxonomy_index`,
which is itself lazily cached) rather than reading the taxonomy xlsx itself.
`is_narrow` runs once per product row in the classify stage's hot loop, so the
caller loads/caches the leaf set once and passes it in on every call.
"""

from __future__ import annotations

from typing import AbstractSet


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


def shares_single_class(codes: list[str]) -> bool:
    """True iff every code shares a single 3-digit class prefix.

    This is necessary but NOT sufficient for `is_narrow` -- it says nothing
    about whether the shared prefix is a taxonomy leaf. Exposed separately so
    config-time validation can flag "this source declared a single-class
    code that isn't a leaf" as a distinct, actionable warning.
    """
    if not codes:
        return False
    prefixes = {c[:4] for c in codes if isinstance(c, str) and len(c) >= 4}
    return len(prefixes) == 1


def is_narrow(codes: list[str], valid_leaves: AbstractSet[str]) -> bool:
    """γ: True iff every code shares a single 3-digit class prefix AND the
    code that prefix resolves to is an actual taxonomy leaf.

    `valid_leaves` is the leaf-code set from
    `coicop_taxonomy.load_taxonomy_index()`; a code absent from the taxonomy
    entirely also fails this check since it cannot be in `valid_leaves`.
    """
    if not shares_single_class(codes):
        return False
    return resolved_code(codes) in valid_leaves


def resolved_code(codes: list[str]) -> str:
    """Most-specific shared code per ADR-0002.

    Single 4-digit code declared → that code. Multiple codes sharing one
    3-digit class → the 3-digit class prefix. Caller must ensure `is_narrow`.
    """
    unique = sorted({c for c in codes if isinstance(c, str) and c})
    if len(unique) == 1:
        return unique[0]
    return unique[0][:4]
