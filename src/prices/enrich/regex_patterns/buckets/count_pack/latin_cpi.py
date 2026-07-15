"""count_pack bucket — CPI-survey count idiom patterns (extract role).

Table-driven via grammar.build_ids from regex_patterns/vocab/count_nouns.yaml.
IDs / declaration order / metadata (script=None, kind=extra_count, sorts LAST in
GOLDEN_EXTRA_COUNT) unchanged.
"""

from __future__ import annotations

from prices.enrich.regex_patterns import grammar
from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = grammar.build_ids(
    "NUM_ROLLS",
    "EN_COMMA_XN",
    "EN_PCS",
    "EN_APOS_S",
    "EN_N_TICKETS",
)
