"""English per-unit pricing-basis markers (extract role).

Emits pricing_basis without an amount_value — used for loose-weight / bulk items
priced per kg or per litre where no numeric quantity appears in the product name.

Examples: "Beef Roast (Per/ Kg)", "Loose Tomatoes Per Kg", "Bulk Olive Oil (Per/ L)".
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # Parens form: (Per/ Kg), (per/KG), (Per/ kg)
    PackPattern(
        id="en_per_kg_parens",
        regex=re.compile(r"\(\s*[Pp]er\s*/?\s*[Kk][Gg]\s*\)"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="mass",
    ),
    # Bare form: "Per Kg", "per kg", "Per KG"
    PackPattern(
        id="en_per_kg_bare",
        regex=re.compile(r"\b[Pp]er\s+[Kk][Gg]\b"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="mass",
    ),
    # Parens form: (Per/ L), (per/l)
    PackPattern(
        id="en_per_l_parens",
        regex=re.compile(r"\(\s*[Pp]er\s*/?\s*[Ll]\s*\)"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="volume",
    ),
    # Bare form: "per liter", "per litre", "Per Liter"
    PackPattern(
        id="en_per_liter_bare",
        regex=re.compile(r"\b[Pp]er\s+[Ll]it(?:er|re)\b"),
        groups=(),
        lang="en",
        role="extract",
        pricing_basis_emit="volume",
    ),
)
