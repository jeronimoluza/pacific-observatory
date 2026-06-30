"""Per-unit pricing-basis marker bucket (extract role).

Records moved VERBATIM from lang/en/per_unit_markers.py, ids renamed to
SCREAMING_SNAKE. Emits pricing_basis without an amount_value — loose-weight / bulk
items priced per kg or per litre. Declaration order matches the pre-reorg
pricing_basis_markers order (PER_KG_PARENS, PER_KG, PER_LITRE_PARENS, PER_LITRE).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # Parens form: (Per/ Kg), (per/KG), (Per/ kg)
    PackPattern(
        id="PER_KG_PARENS",
        regex=re.compile(r"\(\s*[Pp]er\s*/?\s*[Kk][Gg]\s*\)"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="mass",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    # Bare form: "Per Kg", "per kg", "Per KG"
    PackPattern(
        id="PER_KG",
        regex=re.compile(r"\b[Pp]er\s+[Kk][Gg]\b"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="mass",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    # Parens form: (Per/ L), (per/l)
    PackPattern(
        id="PER_LITRE_PARENS",
        regex=re.compile(r"\(\s*[Pp]er\s*/?\s*[Ll]\s*\)"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="volume",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
    # Bare form: "per liter", "per litre", "Per Liter"
    PackPattern(
        id="PER_LITRE",
        regex=re.compile(r"\b[Pp]er\s+[Ll]it(?:er|re)\b"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="volume",
        kind="pricing_basis_marker",
        bucket="per_unit_marker",
    ),
)
