"""Vietnamese extras tagged lang=any in regex_units.yaml::extra_count_markers."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="vi_to_sheets",
        regex=re.compile(r"(?P<count>\d+)\s*Tờ\b"),
        groups=("count",),
        lang="any",
        role="extract",
    ),
)
