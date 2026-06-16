"""English multipack markers — canonicalization role."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # "12 PCS", "8 PCS"
    PackPattern(
        id="multipack_pcs_en",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:PCS|Pcs|pcs|pieces?|pack|PACK|Pack|ct|CT)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="en",
        role="canonicalization",
    ),
)
