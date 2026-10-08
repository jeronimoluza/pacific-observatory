"""thailand: Thai roll and pack counters, and the free-extra marker.

"กระดาษชำระ 32ม้วน" (32 rolls) and "[12 แพ็ค]" / "x 6 แพ็ก" (12 / 6 packs) are
homogeneous packs that the shared counters miss, so these names fell to
review_missing_qty. A name with two such numbers ("6 ม้วน 240 แพ็ค") reads two
sizes and stays one item. "N แถม M" (buy N get M: "4 แถม 2 x 3 แพ็ค") puts more than
the stated pack under the price, so the name is held as a bundle. The pack
word is weak: next to a piece count ("68 ชิ้น x 4 แพค") the name is ambiguous.

Measured 2026-10-08 on the Thailand non-food check (data_refactor): 126
missing_qty products name rolls, 166 name packs.
"""

import re

from prices.enrich.regex_patterns_nonfood import Intent, NFPatch, NFPattern

_F = re.IGNORECASE | re.UNICODE

# Only the numeric form: "4 แถม 2", "5ถุงแถม1ถุง", "x 24 ฟรี 6 ม้วน". A free gift of another
# thing ("แถมไมค์" with a speaker) leaves the item one item.
_TH_FREEBIE = NFPattern(id="TH_FREEBIE", role="bundle", regex=re.compile(r"\d\s*\S{0,6}?\s*(?:แถม|ฟรี)\s*\d", _F))
_TH_PACK = r"(?:แพ็ค|แพ็ก|แพค|แพก)"
# "36 ชิ้น x 4 แพค", "54 ชิ้น 2 แพ็ค", "(50 ชิ้น/แพ็ค) x 20 แพ็ค": M packs of N, the divisor is N x M.
# Read before the roll and pack counters so neither takes half of it.
_TH_N_X_PACKS = NFPattern(
    id="TH_N_X_PACKS",
    role="strong",
    regex=re.compile(
        r"(?<![\w.,/:#-])(?P<n>\d{1,4})(?!\d)\s*(?:ชิ้น|แผ่น|ใบ|ม้วน|ก้อน|ซอง|เม็ด|เส้น)(?:\s*/\s*" + _TH_PACK + r")?\s*\)?"
        r"\s*(?:[x×]\s*)?(?P<a>\d{1,3})(?!\d)\s*" + _TH_PACK, _F),
)
_TH_N_ROLLS = NFPattern(
    id="TH_N_ROLLS",
    role="strong",
    regex=re.compile(r"(?<![\w.,/:#-])(?P<n>\d{1,3})(?!\d)\s*ม้วน", _F),
)
_TH_N_PACK = NFPattern(
    id="TH_N_PACK",
    role="weak",
    regex=re.compile(r"(?<![\w.,/:#-])(?P<n>\d{1,3})(?!\d)\s*(?:แพ็ค|แพ็ก|แพค|แพก)", _F),
)

PATCH = NFPatch(
    additions=(_TH_FREEBIE, _TH_N_X_PACKS, _TH_N_ROLLS, _TH_N_PACK),
    intent={
        "TH_FREEBIE": Intent(
            why="'แถม' (free extra) means more than the stated pack under one price",
            expect="count -> bundle",
            rows=0,
            examples=("Biosafety แปรงสีฟัน แพ็คสุดคุ้ม 4 แถม 2 x 3 แพ็ค",),
        ),
        "TH_N_X_PACKS": Intent(
            why="N ชิ้น x M แพค is M packs of N pieces",
            expect="count N -> count N x M (cartons were read as one pack)",
            rows=0,
            examples=("[ยกลัง] เมอร์รี่ส์ชนิดกางเกงไซส์ L 44 ชิ้น x 3 แพค",),
        ),
        "TH_N_ROLLS": Intent(
            why="'N ม้วน' is N rolls, a homogeneous pack",
            expect="item -> count",
            rows=126,
            examples=("โลตัสซอฟท์กระดาษชำระ 32ม้วน", "สก๊อตต์ ทาวเวล กระดาษอเนกประสงค์ 6 ม้วน"),
        ),
        "TH_N_PACK": Intent(
            why="'N แพ็ค' is N packs, a homogeneous pack",
            expect="item -> count",
            rows=166,
            examples=("[12 แพ็ค] ฟาร์เซ็นท์ แผ่นทําความสะอาดพื้น", "โพลี-ไบรท์ ผ้าเช็ดพื้น x 6 แพ็ก"),
        ),
    },
)
