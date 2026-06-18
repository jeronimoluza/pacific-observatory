"""Vietnamese lang-gated count extras (extract role).

Split from multipack.py: in the consumed extra_count order this marker sorts
after the Latin count markers and before the CPI count idioms, so the file
boundary encodes that ordering (MODULE_ORDER replaces the old _EXTRA_COUNT_ORDER
tuple). Lang-gated to vi to avoid meter clashes.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # '200M' = 200 miếng. Lang-gated to avoid meter clashes.
    # extract-role: no re.IGNORECASE (mirrors extract.py loader).
    PackPattern(
        id="vi_m_pieces",
        regex=re.compile(r"\b(?P<count>\d+)\s*M\b"),
        groups=("count",),
        lang="vi",
        role="extract",
        kind="extra_count",
    ),
)
