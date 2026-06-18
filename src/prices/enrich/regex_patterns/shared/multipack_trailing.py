"""Trailing "Nx" multipack pattern (canonicalization role).

Split from multipack.py: in the consumed canon order the language-specific
multipack_pcs_en (lang/en) sorts between the value+unit multipack patterns and
this trailing-count one, so the file boundary encodes that ordering directly
(MODULE_ORDER replaces the old hand-maintained _CANON_ORDER tuple).
Translated verbatim from static/pack_patterns.yaml.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # Trailing "6X" alone
    PackPattern(
        id="multipack_n_x_only",
        regex=re.compile(r"(?P<count>\d+)\s*[xX×]\s*$", re.IGNORECASE),
        groups=("count",),
        lang="any",
        role="canonicalization",
        kind="canon",
    ),
)
