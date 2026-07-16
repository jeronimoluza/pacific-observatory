"""Multipack bucket — canon multipack/count patterns + N-inner×M-outer multi_pack.

Latin/vi canon patterns (NUM_X_VALUE_UNIT, VALUE_UNIT_X_NUM, NUM_PCS, NUM_PC_GLUED,
NUM_X_TRAILING, LOC_VI, COUNT_UNIT_VI) are now table-driven via grammar.build_ids
(P-class num×measure + C-class count). The CJK records (COUNT_UNIT_ZH, SET_JA, and
the two INNER_X_OUTER multi_pack) stay hand-written — CJK vocab is deferred.
Declaration order (the ordering lever guarded by test_composition_diff) is
preserved: the 7 latin/vi canon first, then the 4 CJK records.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns import grammar
from prices.enrich.regex_patterns.types import PackPattern

_CJK: tuple[PackPattern, ...] = (
    PackPattern(
        id="COUNT_UNIT_ZH",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:入|粒|丸|本|片|盒|個|包|束|件|杯|袋|顆|張|缶|瓶|錠)(?:組|セット|入)?",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="zh",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    PackPattern(
        id="SET_JA",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:本入|束セット|個入|枚入|袋入|セット|組)",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="ja",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    PackPattern(
        id="INNER_X_OUTER_STAR",
        regex=re.compile(
            r"(?P<count>\d+)\s*片\s*[*xX×]\s*(?P<multiplier>\d+)\s*包",
        ),
        groups=("count", "multiplier"),
        lang="any",
        role="extract",
        kind="multi_pack",
        bucket="multipack",
        script="cjk",
    ),
    PackPattern(
        id="INNER_X_OUTER",
        regex=re.compile(
            r"(?P<count>\d+)(?:支|本|片|包|入|個)\s*[*xX×]\s*(?P<multiplier>\d+)(?:組|盒|包|箱)",
        ),
        groups=("count", "multiplier"),
        lang="any",
        role="extract",
        kind="multi_pack",
        bucket="multipack",
        script="cjk",
    ),
)

PATTERNS: tuple[PackPattern, ...] = (
    grammar.build_ids(
        "NUM_X_VALUE_UNIT",
        "VALUE_UNIT_X_NUM",
        "NUM_PCS",
        "NUM_PC_GLUED",
        "NUM_X_TRAILING",
        "LOC_VI",
        "COUNT_UNIT_VI",
    )
    + _CJK
)
