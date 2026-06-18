"""Vietnamese multipack markers — canonicalization role.

The lang-gated count extra `vi_m_pieces` lives in count_markers.py: in the
consumed extra_count order it sorts after the Latin count markers, whereas these
canon multipack patterns sort early — a single module cannot occupy both
positions, so the extract-role marker is split out (Phase 0.5 / Plan 04).
"""

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
        kind="canon",
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
        kind="canon",
    ),
)
