"""Chinese multipack patterns — canonicalization role.

The zh volume/mass pattern lives in volume_mass.py: in the consumed canon order
it sorts last (after the Japanese kana set and the shared value+unit pattern),
whereas this count-unit multipack sorts earlier — a single module cannot occupy
both positions, so the volume/mass pattern is split out (Phase 0.5 / Plan 04).
"""

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
        kind="canon",
    ),
)
