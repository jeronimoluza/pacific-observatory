"""emartmall: a trailing "(Kg)" prices the item by the kilogram; a nearby
per-piece weight note is not the sold size.

Loose produce, meat and fish carry "(Kg)" right after the name to say the
price is per kilogram, sometimes next to an informational note on how much
one piece weighs: "Cam Navel Xuất Xứ Úc (Kg) ~0.3Kg/Trái", "Bắp Cải Trái Tim
(Kg) ~0.3Kg/Bắp", "Cải Thảo ~0.6Kg/Cái (Kg)", "Cá Hú Nguyên Con Không Làm Sẵn
(Kg) Giá bán theo kg~1.1Kg/Con". The shared measure pattern reads the note's
number as the product's size, so "(Kg)" items with a note price ~3-13x too
high per kg. The note's unit sits before the slash and the piece word after
it ("~0.3Kg/Trái"); that order is reversed from the "pieces per kg" ratio
some names also carry ("5~6 Trái/Kg", left alone: unit after the slash).

These two canon patterns match "(Kg)" together with the note (either order)
and capture nothing (no value, no count, no unit): a pack pattern with no
groups still wins its slot by matching first (source patterns go first in
their bucket) and returns nothing, so the shared measure pattern that would
otherwise read the note's number never runs. With no pack-unit candidate,
`decide()` falls through to the untouched, independently-matched bare "Kg"
marker (BARE_KG, `pack_basis.yaml`) already present in every one of these
names, which sets mass at its usual default of 1 kg -- the same path a
plain "(Kg)" name with no note takes.

An earlier version of this patch captured a "unit" group from the literal
"(Kg)", which also blocked the wrong measure but, because a pack-pattern
candidate with a unit and no value outranks the marker rung in decide(),
left amount_value at NaN (`review_uv_unscored`) instead of reaching the
marker's 1 kg default. Confirmed by inspecting `extract.py`/`extract_decide.py`
and diffing rulecheck's output between the two versions.

Measured 2026-09-26 on products_input (09-20), via rulecheck: 25 emartmall
names carry a note after "(Kg)" or before it, 167 rows total (159 + 8), all
mass -> mass, amount 1 kg, 0 count lost, 0 rows outside vietnam.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_NOUN = r"(?:trái|quả|con|củ|cái|bông|bắp)"
_NOTE = rf"~?\s*\d+(?:[.,]\d+)?(?:\s*[-~]\s*\d+(?:[.,]\d+)?)?\s*(?:g|gr|gam|kg)\b.{{0,15}}?/\s*{_NOUN}\b"

_KG_THEN_NOTE = PackPattern(
    id="EMART_KG_PAREN_THEN_NOTE",
    regex=re.compile(rf"(?i)\(kg\).{{0,30}}?{_NOTE}"),
    groups=(),
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)
_NOTE_THEN_KG = PackPattern(
    id="EMART_NOTE_THEN_KG_PAREN",
    regex=re.compile(rf"(?i){_NOTE}.{{0,10}}?\(kg\)"),
    groups=(),
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)

PATCH = SourcePatch(
    additions=(_KG_THEN_NOTE, _NOTE_THEN_KG),
    intent={
        "EMART_KG_PAREN_THEN_NOTE": Intent(
            why="'(Kg) ~Xg|kg/<piece>' notes a piece weight; the price is still per kg",
            expect="mass -> mass",
            rows=159,
            examples=(
                "Cam Navel Xuất Xứ Úc (Kg) ~0.3Kg/Trái",
                "Bắp Cải Trái Tim (Kg) ~0.3Kg/Bắp",
                "Xoài Cát Hòa Lộc (Kg) ~400G/Trái",
                "Cá Thu Đao Nguyên Con Không Làm Sẵn (Kg)~0.1Kg/Con",
                "Cá Hú Nguyên Con Không Làm Sẵn (Kg) Giá bán theo kg~1.1Kg/Con",
            ),
        ),
        "EMART_NOTE_THEN_KG_PAREN": Intent(
            why="'~Xkg/<piece> (Kg)' notes a piece weight before the per-kg marker",
            expect="mass -> mass",
            rows=8,
            examples=(
                "Cải Thảo ~0.6Kg/Cái (Kg)",
            ),
        ),
    },
)
