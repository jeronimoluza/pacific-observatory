"""count_pack bucket — Latin-script count markers (extract role).

Table-driven: the enumerated per-noun/case patterns are now generated from
regex_patterns/vocab/count_nouns.yaml via grammar.build_ids (C-class, the
<num><noun> production). Adding a count noun is a table edit, not a new regex.
IDs / declaration order / metadata (script=latin, kind=extra_count) unchanged.
"""

from __future__ import annotations

from prices.enrich.regex_patterns import grammar
from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = grammar.build_ids(
    "EN_CAPS",
    "EN_TABLETS",
    "EN_SACHETS",
    "EN_SHEETS",
    "EN_PACK_OF",
    "EN_N_PACK",
    "EN_N_INDIVIDUAL_PACK",
    "EN_HALF_DOZEN",
    "EN_DOZEN",
    "EN_TWIN_PACK",
    "EN_TRIPLE_PACK",
    "EN_DOUBLE_PACK",
)
