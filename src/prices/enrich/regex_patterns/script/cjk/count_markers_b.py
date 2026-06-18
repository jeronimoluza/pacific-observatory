"""CJK count markers, part 2 (extract role).

Split from count_markers.py: in the consumed extra_count order the
script-agnostic `vi_to_sheets` marker sorts between cjk_numeral_set and these,
so the file boundary encodes that ordering directly (MODULE_ORDER replaces the
old hand-maintained _EXTRA_COUNT_ORDER tuple). Translated verbatim from
regex_units.yaml::extra_count_markers.
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
    )


PATTERNS: tuple[PackPattern, ...] = (
    _p("cjk_ko_pcs", r"(?P<count>\d+)\s*(?:개|매|병|봉|장|회)", ("count",)),
    _p(
        "cjk_n_x_count",
        r"\bM?[xX×]\s*(?P<count>\d+)\s*(?:組|セット|本|入|片|盒|個|包|束|件|杯|袋|張)\b",
        ("count",),
    ),
    _p(
        "cjk_double_pack",
        r"\b(?:ダブルパック|ツインパック|デュアルパック)\b",
        (),
        fixed_count=2,
    ),
)
