"""Retailer-boilerplate stripping for product names.

Removes bracket / quote / paren-delimited segments whose sense is unambiguous
retailer boilerplate — stock status, pickup / collection location, branch
availability, expiry, prescription-required, notice-required, brand-may-vary,
and pure-digit SKU codes — while preserving quantity, pack, and pricing-basis
segments. Runs in stages/prepare before canonical-key derivation so the cleaned
name propagates identically to dedupe, label_store, lexicon, tier-b, the
classifier, and gold labeling.

Conservative by design: only delimited segments are eligible, and a segment is
stripped only when its sense matches the boilerplate lexicon (or it is a SKU
code) AND it carries no quantity / pack / pricing-basis token. Product
attributes (origin, halal, refrigerated, retailer/promo tags) are kept.

Pure functions, no I/O.
"""

from __future__ import annotations

import re

# Delimited segments: [...], "...", curly "...", (...).
_SEGMENT = re.compile(r'\[[^\]]*\]|"[^"]*"|“[^”]*”|\([^)]*\)')

# Quantity / pack / pricing-basis guard: a matching segment is never stripped.
_QTY_GUARD = re.compile(
    r"""
      \d\s*(?:kg|kgs|g|gr|gm|mg|ml|cl|l|lt|ltr|litre|liter|oz|lb|lbs|
             pack|pk|pcs|pc|ct|count|tab|tabs|tablet|cap|caps|capsule|
             rolls?|sheets?|bottle|btl|botol|viên|입|정|매|
             pairs?|dozen)
    | \bx\s*\d
    | \d\s*x\b
    | bundle\s+of\s+\d
    | \bper\s*/?\s*(?:kg|kgs|g|gr|ml|l|lt|ltr|oz|lb|pcs?|pc|tab|tablet|
             botol|bottle|item|unit|piece|each|serving|roll|sheet)\b
    """,
    re.IGNORECASE | re.VERBOSE | re.UNICODE,
)

# Boilerplate senses, matched against a segment's inner text.
_SENSE = re.compile(
    r"""
      sold\s*out
    | out\s+of\s+stock
    | \bin\s+stock\b
    | limited\s+stock
    | stock\s+may\s+vary
    | pick\s*up\s+(?:from|at)
    | pickup\s+(?:from|at)
    | collect\s+(?:from|at)
    | not\s+avail
    | prescription\s+required
    | \bexpiry\b
    | \bexp\.?\s*:
    | best\s+before
    | notice\s+required
    | brand\s+may\s+vary
    """,
    re.IGNORECASE | re.VERBOSE,
)

# SKU code: inner text is a single digit run or slash-separated digit groups
# (no internal spaces — that would be a size run like "80 90 100"), with >=5
# digits total or a slash between groups (keeps bare 4-digit years "(2024)").
_SKU_SHAPE = re.compile(r"^\s*\d[\d/]*\d\s*$")


def _is_sku(inner: str) -> bool:
    if not _SKU_SHAPE.match(inner):
        return False
    digits = re.sub(r"\D", "", inner)
    return len(digits) >= 5 or "/" in inner


def _seg_is_boilerplate(seg: str) -> bool:
    if _QTY_GUARD.search(seg):
        return False
    inner = seg[1:-1]
    if _is_sku(inner):
        return True
    return bool(_SENSE.search(inner))


def strip_boilerplate(name) -> str:
    """Return `name` with boilerplate segments removed. Names carrying no
    boilerplate are returned unchanged; never returns empty (falls back to the
    original when stripping would erase everything)."""
    if not isinstance(name, str):
        name = "" if name is None else str(name)
    removed = False

    def _repl(m):
        nonlocal removed
        if _seg_is_boilerplate(m.group(0)):
            removed = True
            return ""
        return m.group(0)

    cleaned = _SEGMENT.sub(_repl, name)
    if not removed:
        return name
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"\s*[-–—]\s*$", "", cleaned).strip()
    cleaned = re.sub(r"^\s*[-–—]\s*", "", cleaned).strip()
    return cleaned or name.strip()
