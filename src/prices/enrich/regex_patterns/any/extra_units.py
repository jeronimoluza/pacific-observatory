"""Extra unit patterns (extract role) for units pack_patterns deliberately excludes.

Translated from static/regex_units.yaml::extra_units. cl and Vietnamese "lít"
both fall through the canonicalization layer (which only recognises the
ml/l/kg/g/oz/lb family); they appear here so tier-a still emits the right
(basis, su, mul) tuple.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern, UnitEmit

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="cl_volume",
        regex=re.compile(
            r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?)\s*(?:cl|CL|cL|Cl)\b",
        ),
        groups=("value",),
        lang="any",
        role="extract",
        unit_emit=UnitEmit(basis="volume", su="lt", mul=0.01),
    ),
    PackPattern(
        id="vi_lit_volume",
        regex=re.compile(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*l[íi]t",
        ),
        groups=("value",),
        lang="any",
        role="extract",
        unit_emit=UnitEmit(basis="volume", su="lt", mul=1.0),
    ),
)
