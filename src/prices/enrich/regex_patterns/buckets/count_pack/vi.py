"""count_pack bucket — Vietnamese lang-gated count extra (extract role).

Table-driven via grammar.build_ids from regex_patterns/vocab/count_nouns.yaml.
'200M' = 200 miếng. lang=vi, script=None, kind=extra_count — unchanged.
"""

from __future__ import annotations

from prices.enrich.regex_patterns import grammar
from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = grammar.build_ids("VI_PIECES")
