"""English multipack markers — canonicalization role."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # "12 PCS", "8 PCS". Word-boundary lookbehind (?<!\w) prevents SKU tails
    # like `15CT` in `SM15CT` from being read as count=15 (2026-06-16, surfaced
    # by VN kitchen-cabinet gold rows during tier-a precision lift).
    PackPattern(
        id="multipack_pcs_en",
        regex=re.compile(
            r"(?<!\w)(?P<count>\d+)\s*(?:PCS|Pcs|pcs|pieces?|pack|PACK|Pack|ct|CT)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="en",
        role="canonicalization",
        kind="canon",
    ),
)
