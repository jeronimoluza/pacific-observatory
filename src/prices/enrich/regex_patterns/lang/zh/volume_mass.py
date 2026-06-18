"""Chinese volume/mass value+unit pattern — canonicalization role.

Split from multipack.py: in the consumed canon order this sorts last (after the
shared value+unit pattern), so the file boundary encodes that ordering
(MODULE_ORDER replaces the old _CANON_ORDER tuple).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
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
        kind="canon",
    ),
)
