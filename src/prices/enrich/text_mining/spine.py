"""Structural-span spine — separates the structural span (amount / count /
multipack / promo / unit) from the identity span on the RAW surface form.

This module is a thin WRAPPER over the cascade's own tier-a machinery. It
authors no quantity/pack/unit regexes of its own: a parallel regex set would
silently diverge from tier-a. The identity span comes from
`normalize.extract_pack` (its first return is the name with the structural pack
removed); the structural fields come from `extract.extract`. Both are called on
`product_name_original` (raw surface) — never on `canonical_strict`, which
sorts tokens and strips the pack, destroying the structural-span signal.

`structural_span_density` reports the fraction of rows carrying a structural
span — the tier-a ceiling metric for the Layer-0 corpus probe.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.extract import extract
from prices.enrich.normalize import extract_pack

_NAME_COL = "product_name_original"


def _has_structural_span(amount_value, count, multiplier) -> bool:
    return (
        amount_value is not None
        or (count or 1) > 1
        or bool(multiplier and multiplier > 1)
    )


def split_spans(product_name: str, lang: str | None) -> dict:
    """Split a raw product name into its identity span and structural span.

    Returns the identity span (pack removed) plus the tier-a structural fields
    and a `has_structural_span` boolean. Structural fields are identical to
    `extract.extract(product_name, None, None, lang)` field-for-field.
    """
    identity_span, _count, _value, _unit = extract_pack(product_name, lang)
    sf = extract(product_name, category=None, country=None, lang=lang)
    return {
        "identity_span": identity_span,
        "pricing_basis": sf.pricing_basis,
        "amount_value": sf.amount_value,
        "standard_unit": sf.standard_unit,
        "count": sf.count,
        "multiplier": sf.multiplier,
        "is_promotion": sf.is_promotion,
        "is_bundle": sf.is_bundle,
        "is_multipack": sf.is_multipack,
        "has_structural_span": _has_structural_span(
            sf.amount_value, sf.count, sf.multiplier
        ),
    }


def _row_has_structural_span(name: str, lang: str | None) -> bool:
    return split_spans(name, lang)["has_structural_span"]


def structural_span_density(
    frame: pd.DataFrame,
    by: str | None = None,
) -> float | pd.Series:
    """Fraction of rows whose raw name carries a structural span (in [0, 1]).

    This is the tier-a ceiling for the Layer-0 report. Reads
    `product_name_original` (raw surface) and the per-row `lang`. When `by` is
    given, returns a per-group Series of densities; otherwise a single float.
    Empty frame → 0.0.
    """
    if frame.empty:
        if by is not None:
            return pd.Series(dtype=float)
        return 0.0

    langs = frame["lang"] if "lang" in frame.columns else [None] * len(frame)
    flags = [
        _row_has_structural_span(name, lang)
        for name, lang in zip(frame[_NAME_COL], langs, strict=False)
    ]
    flag_series = pd.Series(flags, index=frame.index, dtype=float)

    if by is not None:
        return flag_series.groupby(frame[by]).mean()
    return float(flag_series.mean())
