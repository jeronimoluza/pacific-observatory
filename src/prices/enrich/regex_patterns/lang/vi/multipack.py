"""Vietnamese multipack markers + lang-gated count extras."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="multipack_vi_loc",
        regex=re.compile(
            r"\b(?:Lốc|lốc|Thùng|thùng|Hộp|hộp|Bộ|bộ|Combo|combo|Set|set)\s+(?P<count>\d+)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="vi",
        role="canonicalization",
    ),
    PackPattern(
        id="multipack_vi_count_unit",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:cái|cây|gói|chai|lon|chiếc|hộp|bịch)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="vi",
        role="canonicalization",
    ),
    # '200M' = 200 miếng. Lang-gated to avoid meter clashes.
    # extract-role: no re.IGNORECASE (mirrors extract.py loader).
    PackPattern(
        id="vi_m_pieces",
        regex=re.compile(r"\b(?P<count>\d+)\s*M\b"),
        groups=("count",),
        lang="vi",
        role="extract",
    ),
)
