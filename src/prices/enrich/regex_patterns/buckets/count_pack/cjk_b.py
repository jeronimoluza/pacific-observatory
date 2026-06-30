"""count_pack bucket — CJK count markers, part 2 (extract role).

Records moved VERBATIM from script/cjk/count_markers_b.py, ids renamed to
SCREAMING_SNAKE. Split from cjk.py because in GOLDEN_EXTRA_COUNT the
script-agnostic VI_TO_SHEETS sorts between CJK_NUMERAL_SET and these — the file
boundary is the ordering lever. script="cjk" (was under script/cjk/).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern


def _p(
    id_: str,
    regex: str,
    groups: tuple[str, ...],
    fixed_count: int | None = None,
) -> PackPattern:
    return PackPattern(
        id=id_,
        regex=re.compile(regex),
        groups=groups,
        lang="any",
        role="extract",
        fixed_count=fixed_count,
        kind="extra_count",
        bucket="count_pack",
        script="cjk",
    )


PATTERNS: tuple[PackPattern, ...] = (
    _p("CJK_KO_PCS", r"(?P<count>\d+)\s*(?:개|매|병|봉|장|회)", ("count",)),
    _p(
        "CJK_N_X_COUNT",
        r"\bM?[xX×]\s*(?P<count>\d+)\s*(?:組|セット|本|入|片|盒|個|包|束|件|杯|袋|張)\b",
        ("count",),
    ),
    _p(
        "CJK_DOUBLE_PACK",
        r"\b(?:ダブルパック|ツインパック|デュアルパック)\b",
        (),
        fixed_count=2,
    ),
)
