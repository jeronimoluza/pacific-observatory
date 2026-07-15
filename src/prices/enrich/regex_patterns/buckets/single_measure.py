"""Single value+unit bucket — the canon mass/volume pair + extra-unit fall-throughs.

The latin canon measure (VALUE_UNIT, M-class) and the extra-unit fallbacks
(CENTILITRE, LITRE_VI) are table-driven via grammar.build_ids from
regex_patterns/vocab/{units,pack_basis}.yaml. VALUE_UNIT keeps suppress_window=20
(BUG 3 / BUG 4, load-bearing). The CJK VALUE_UNIT_ZH stays hand-written.
Declaration order preserved: VALUE_UNIT, VALUE_UNIT_ZH, CENTILITRE, LITRE_VI.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns import grammar
from prices.enrich.regex_patterns.types import PackPattern

_VALUE_UNIT_ZH = PackPattern(
    id="VALUE_UNIT_ZH",
    regex=re.compile(
        r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>公升|毫升|公斤|公克|克|升)",
        re.IGNORECASE,
    ),
    groups=("value", "unit"),
    lang="zh",
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)

PATTERNS: tuple[PackPattern, ...] = (
    grammar.build_ids("VALUE_UNIT")
    + (_VALUE_UNIT_ZH,)
    + grammar.build_ids("CENTILITRE", "LITRE_VI")
)
