"""Japanese kana multipack markers — canonicalization role."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="multipack_ja_kana_set",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:本入|束セット|個入|枚入|袋入|セット|組)",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="ja",
        role="canonicalization",
        kind="canon",
    ),
)
