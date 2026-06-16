"""Chinese multipack + volume/mass patterns — canonicalization role."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="multipack_zh_count_unit",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:入|粒|本|片|盒|個|包|束|件|杯|袋|顆|張)(?:組|セット|入)?",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="zh",
        role="canonicalization",
    ),
    # "500毫升" "1公升" "200公克" "2公斤" "50克"
    PackPattern(
        id="zh_volume_mass",
        regex=re.compile(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>公升|毫升|公斤|公克|克|升)",
            re.IGNORECASE,
        ),
        groups=("value", "unit"),
        lang="zh",
        role="canonicalization",
    ),
)
