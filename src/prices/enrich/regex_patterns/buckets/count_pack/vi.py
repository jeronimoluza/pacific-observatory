"""count_pack bucket — Vietnamese lang-gated count extra (extract role).

Record moved VERBATIM from lang/vi/count_markers.py (lang="vi"), id renamed to
SCREAMING_SNAKE. In GOLDEN_EXTRA_COUNT this sits BETWEEN the Latin run and the CPI
run, so it is its own module — the file boundary is the ordering lever.
script=None (was under lang/vi/).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # '200M' = 200 miếng. Lang-gated to avoid meter clashes.
    # extract-role: no re.IGNORECASE (mirrors extract.py loader).
    PackPattern(
        id="VI_PIECES",
        regex=re.compile(r"\b(?P<count>\d+)\s*M\b"),
        groups=("count",),
        lang="vi",
        role="extract",
        kind="extra_count",
        bucket="count_pack",
    ),
)
