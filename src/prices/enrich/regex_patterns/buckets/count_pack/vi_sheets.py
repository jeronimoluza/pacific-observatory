"""count_pack bucket — Vietnamese "N Tờ" sheet marker (extract role).

Record moved VERBATIM from shared/vi_extras.py (lang="any"), id renamed to
SCREAMING_SNAKE. In GOLDEN_EXTRA_COUNT this sits BETWEEN the two CJK runs (cjk.py
and cjk_b.py), so it is its own module — the file boundary is the ordering lever.
script=None (was under shared/).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="VI_TO_SHEETS",
        regex=re.compile(r"(?P<count>\d+)\s*Tờ\b"),
        groups=("count",),
        lang="any",
        role="extract",
        kind="extra_count",
        bucket="count_pack",
    ),
)
