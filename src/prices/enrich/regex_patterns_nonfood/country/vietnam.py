"""vietnam: Vietnamese piece counters and pack words.

"2 miếng dán", "4 Viên AAA", "(50 gói)", "hộp 20 miếng" are homogeneous packs:
the shared counters (cái, chiếc) miss them, so these names fell to one item.
"Hộp N" (box of N) and "vỉ N" (blister of N) put the number after the pack word.

Measured 2026-10-06 on the Vietnam Stage B pilot (data_refactor, piece
leaves): 3,000 products go item -> count (2,289 by the counter, 1,118 by the
box word; some by both). 18 of a 20-product hand sample right; of the two
misses, "Tặng thêm 6 miếng" is now a freebie bundle and "Combo 4 Gói ... (28
Miếng)" stays one item (two pack sizes, ambiguous).
"""

import re

from prices.enrich.regex_patterns_nonfood import Intent, NFPatch, NFPattern

_F = re.IGNORECASE | re.UNICODE

_VI_COUNTER = NFPattern(
    id="VI_N_COUNTER",
    role="strong",
    regex=re.compile(r"(?<![\w.,/:#-])(?P<n>\d{1,4})(?!\d)\s*(?:miếng|viên|gói|cuốn|cây|tấm|ống)(?![a-zà-ỹ])", _F),
)
_VI_BOX_OF_N = NFPattern(
    id="VI_BOX_OF_N",
    role="strong",
    regex=re.compile(r"\b(?:hộp|vỉ|túi)\s+(?P<n>\d{1,4})(?!\d)(?!\s*(?:ml|l|g|kg|gr|cm|mm|m)\b)", _F),
)

PATCH = NFPatch(
    additions=(_VI_COUNTER, _VI_BOX_OF_N),
    intent={
        "VI_N_COUNTER": Intent(
            why="Vietnamese piece counters after the number are a homogeneous pack",
            expect="item -> count",
            rows=2289,
            examples=("2 miếng dán TPU đồng hồ MiBand 4", "Pin sạc AAA NiMH 1300mah (4 Viên AAA)",
                      "Hỗn hợp rửa mũi NeilMed Sinus Rinse (50 gói)"),
        ),
        "VI_BOX_OF_N": Intent(
            why="'hộp N' / 'vỉ N' / 'túi N' put the pack size after the pack word",
            expect="item -> count",
            rows=1118,
            examples=("Hộp 12 Bút Lông Màu Acrylic Marker Pen", "Hộp 5 Bút Kaco 5 Màu Cao Cấp"),
        ),
    },
)
