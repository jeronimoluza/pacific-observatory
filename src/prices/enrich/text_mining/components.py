"""Decompose a raw product name into the six MI components.

The component set the Layer-1 MI backbone scores against COICOP leaf and
unit-dimension: {brand, identity_noun, dimension, magnitude, pack, breadcrumb}.

This module composes the modules that already own each signal — it re-derives
nothing:

- dimension  = spine.split_spans(...)["pricing_basis"]  (tier-a unit dimension)
- magnitude  = spine.split_spans(...)["amount_value"]    (tier-a amount value)
- pack       = a descriptor built from spine's count / multiplier (or None)
- identity_noun = segment.segment_auto on the spine's identity span (pack
                  removed), joined back to a token string
- brand      = normalize.canonicalize(...).brand
- breadcrumb = normalize.normalize_breadcrumb(category)

An empty name yields all-None components (breadcrumb is the empty string, the
normalize_breadcrumb contract for no input) without raising.
"""

from __future__ import annotations

from prices.enrich.normalize import canonicalize, normalize_breadcrumb
from prices.enrich.text_mining.segment import segment_auto
from prices.enrich.text_mining.spine import split_spans


def _pack_descriptor(count, multiplier) -> str | None:
    """A compact pack token from the tier-a count / multiplier, or None.

    count is the per-pack unit count (e.g. x6); multiplier is a bundle factor
    (e.g. 2 x ...). Reuses spine's already-parsed structural fields — no new
    pack regex. Returns None when neither indicates a multi-unit pack.
    """
    parts: list[str] = []
    if count and count > 1:
        parts.append(f"x{int(count)}")
    if multiplier and multiplier > 1:
        parts.append(f"*{int(multiplier)}")
    return " ".join(parts) if parts else None


def _identity_noun(identity_span: str, lang: str | None) -> str | None:
    """Segmented identity tokens joined back to a string (None when empty).

    The identity span is the name with the structural pack already removed by
    the spine; segment_auto routes by detected script so CJK/Thai/Hangul rows
    are tokenised correctly and Latin rows split on whitespace.
    """
    if not identity_span or not identity_span.strip():
        return None
    tokens = [t for t in segment_auto(identity_span.strip()) if t.strip()]
    if not tokens:
        return None
    return " ".join(tokens)


def decompose(name: str, lang: str | None, category: str | None) -> dict:
    """Split a raw product name into the six MI components.

    Returns a dict with keys brand, identity_noun, dimension, magnitude, pack,
    breadcrumb. dimension/magnitude come straight from spine.split_spans (the
    tier-a pricing_basis / amount_value) and are never re-derived here.
    """
    breadcrumb = normalize_breadcrumb(category)
    if not name or not name.strip():
        return {
            "brand": None,
            "identity_noun": None,
            "dimension": None,
            "magnitude": None,
            "pack": None,
            "breadcrumb": breadcrumb,
        }

    spans = split_spans(name, lang)
    canon = canonicalize(name, category, "", lang)
    return {
        "brand": canon.brand,
        "identity_noun": _identity_noun(spans["identity_span"], lang),
        "dimension": spans["pricing_basis"],
        "magnitude": spans["amount_value"],
        "pack": _pack_descriptor(spans["count"], spans["multiplier"]),
        "breadcrumb": breadcrumb,
    }
