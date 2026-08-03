"""Per-unit pricing-basis marker bucket (extract role).

Table-driven via grammar.build_ids from regex_patterns/vocab/pack_basis.yaml
(B-class: per UNIT). Emits pricing_basis without an amount_value — loose-weight /
bulk items priced per kg or per litre. IDs / declaration order / metadata
(lang=en, kind=pricing_basis_marker) unchanged.
"""

from __future__ import annotations

from prices.enrich.regex_patterns import grammar
from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = grammar.build_ids(
    "PER_KG_PARENS",
    "PER_KG",
    "PER_LITRE_PARENS",
    "PER_LITRE",
    "SLASH_KG",
    "BARE_KG",
    "SLASH_LITRE",
)
