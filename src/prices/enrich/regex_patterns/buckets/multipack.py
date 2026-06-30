"""Multipack bucket — canon multipack count patterns + N-inner×M-outer multi_pack.

Records moved VERBATIM (regex/groups/lang/role unchanged) from the pre-reorg
modules shared/multipack.py, lang/en/multipack.py, shared/multipack_trailing.py,
lang/vi/multipack.py, lang/zh/multipack.py, lang/ja/multipack.py (the 9 canon)
and script/cjk/multi_pack.py (the 2 multi_pack), with ids renamed to
SCREAMING_SNAKE. Declaration order reproduces GOLDEN_CANON's 9 multipack-canon
positions, then GOLDEN_MULTI_PACK (star, full). multipack.py precedes
single_measure.py in MODULE_ORDER so the value+unit canon pair lands at the canon
tail.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # "20x1.5g", "4x90g", "12 x 500ml"  → count=20, value=1.5, unit=g
    PackPattern(
        id="NUM_X_VALUE_UNIT",
        regex=re.compile(
            r"(?P<count>\d+)\s*[x×X]\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB)\b",
            re.IGNORECASE,
        ),
        groups=("count", "value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    # "5kg(5kg×1)" or "5kg x 1" — pack-of-1 explicit  → count=1, value=5, unit=kg
    PackPattern(
        id="VALUE_UNIT_X_NUM",
        regex=re.compile(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB)\s*[x×X]\s*(?P<count>\d+)\b",
            re.IGNORECASE,
        ),
        groups=("count", "value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    # "12 PCS", "8 PCS". Word-boundary lookbehind (?<!\w) prevents SKU tails
    # like `15CT` in `SM15CT` from being read as count=15 (2026-06-16, surfaced
    # by VN kitchen-cabinet gold rows during tier-a precision lift).
    PackPattern(
        id="NUM_PCS",
        regex=re.compile(
            r"(?<!\w)(?P<count>\d+)\s*(?:PCS|Pcs|pcs|pieces?|pack|PACK|Pack|ct|CT)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="en",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    # Glued singular "Npc" — "(5pc)", "3PC", "2pc". GLUED only (no \s*) and
    # `(?!s)` so the spaced "N PC" (personal computer) and the plural "Npcs"
    # (handled above) never hit this; `(?<!\w)` guards SKU tails (2026-06-25).
    PackPattern(
        id="NUM_PC_GLUED",
        regex=re.compile(r"(?<!\w)(?P<count>\d+)pc\b(?!s)", re.IGNORECASE),
        groups=("count",),
        lang="en",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    # Trailing "6X" alone
    PackPattern(
        id="NUM_X_TRAILING",
        regex=re.compile(r"(?P<count>\d+)\s*[xX×]\s*$", re.IGNORECASE),
        groups=("count",),
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    PackPattern(
        id="LOC_VI",
        regex=re.compile(
            r"\b(?:Lốc|lốc|Thùng|thùng|Hộp|hộp|Bộ|bộ|Combo|combo|Set|set)\s+(?P<count>\d+)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="vi",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    PackPattern(
        id="COUNT_UNIT_VI",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:cái|cây|gói|chai|lon|chiếc|hộp|bịch|viên|miếng)\b",
            re.IGNORECASE,
        ),
        groups=("count",),
        lang="vi",
        role="canonicalization",
        kind="canon",
        bucket="multipack",
    ),
    PackPattern(
        id="COUNT_UNIT_ZH",
        regex=re.compile(
            r"(?P<count>\d+)\s*(?:入|粒|丸|本|片|盒|個|包|束|件|杯|袋|顆|張)(?:組|セット|入)?",
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
