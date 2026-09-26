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
and read only the literal "Kg" in "(Kg)" as the unit, not the note's number,
so the row falls back to the existing bare "(Kg)" convention (mass, amount
1 kg) exactly like a "(Kg)" name with no note.

Measured 2026-09-26 on products_input (09-20), via rulecheck: 25 emartmall
names carry a note after "(Kg)" or before it, 167 rows total (159 + 8), all
mass -> mass (amount corrected to 1 kg), 0 count lost, 0 rows outside
vietnam.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_NOUN = r"(?:trái|quả|con|củ|cái|bông|bắp)"
_NOTE = rf"~?\s*\d+(?:[.,]\d+)?(?:\s*[-~]\s*\d+(?:[.,]\d+)?)?\s*(?:g|gr|gam|kg)\b.{{0,15}}?/\s*{_NOUN}\b"

_KG_THEN_NOTE = PackPattern(
    id="EMART_KG_PAREN_THEN_NOTE",
    regex=re.compile(rf"(?i)\((?P<unit>kg)\).{{0,30}}?{_NOTE}"),
    groups=("unit",),
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)
_NOTE_THEN_KG = PackPattern(
    id="EMART_NOTE_THEN_KG_PAREN",
    regex=re.compile(rf"(?i){_NOTE}.{{0,10}}?\((?P<unit>kg)\)"),
    groups=("unit",),
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
