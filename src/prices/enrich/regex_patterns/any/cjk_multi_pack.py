"""CJK multi-pack markers (extract role) — N inner × M outer.

Translated from regex_units.yaml::multi_pack_markers. When matched, the count
group is N (per-inner) and the multiplier group is M (outer container count).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="cjk_inner_outer_star",
        regex=re.compile(
            r"(?P<count>\d+)\s*片\s*[*xX×]\s*(?P<multiplier>\d+)\s*包",
        ),
        groups=("count", "multiplier"),
        lang="any",
        role="extract",
    ),
    PackPattern(
        id="cjk_inner_outer_full",
        regex=re.compile(
            r"(?P<count>\d+)(?:支|本|片|包|入|個)\s*[*xX×]\s*(?P<multiplier>\d+)(?:組|盒|包|箱)",
        ),
        groups=("count", "multiplier"),
        lang="any",
        role="extract",
    ),
)
