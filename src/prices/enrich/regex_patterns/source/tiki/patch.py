"""tiki: a case or combo of N one-measure units keeps its N.

"Thùng 12 hộp sữa ... 1 Lít" is a case of twelve one-litre cartons. The shared
buckets read the litre through the extra_unit LITRE_VI, and decide's extra-unit
rung emits multiplier 1, so the case priced as a single litre -- 12x too high a
unit value, on milk and cooking oil. These two canon patterns read the case
count and the litre together, so the pack rung sets multiplier = N (volume
always multiplies). A count noun (hộp/chai/lon/bình) must precede the litres,
which keeps appliance capacities ("Tủ Chống Ẩm ... (80 Lít)") out.

Named gap 1 of rung 1a (00-SPEC.md). Measured 2026-09-24 on products_input
(09-20): 29 tiki rows move, 0 lose a count.

"N gói ... mỗi gói Xg|gr|gam" states a per-sachet weight and the sachet count
separately ("DAMODE 58 gói màu đỏ mỗi gói 2,2gr"); the shared gram pattern
reads only the per-sachet number, so the row prices at 1/N of its true total
weight. This canon pattern reads the count and the per-sachet weight together
and multiplies.

Measured 2026-09-26 on products_input (09-20): 18 tiki names move mass ->
mass, 0 count lost (rulecheck); 2 more names matching the same text shape
("Combo ..." prefix) already resolve through an earlier pattern and are left
alone.

"Combo A Thùng B hộp|chai|lon ... V ml" (2026-09-27) is A cases of B units of
V: "Combo 2 Thùng 36 hộp sữa ... 180ml" is 72 x 180 ml. The shared LOC_VI read
only the combo's A, pricing two cases as two cartons.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_LIT = r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>l)[íi]t(?![^\W\d_])"  # unit "l" -> litres

_CASE_N_LIT = PackPattern(
    id="TIKI_CASE_N_LIT",
    regex=re.compile(
        rf"(?i)(?:^\s*|(?:thùng|combo|lốc)\s*)(?P<count>\d+)\s*(?:hộp|chai|lon|bình)\b.*?{_LIT}"
    ),
    groups=("count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)
_N_X_LIT = PackPattern(
    id="TIKI_N_X_LIT",
    regex=re.compile(rf"(?i)(?P<count>\d+)\s*(?:hộp|chai|lon|bình)\s*[x×]\s*{_LIT}"),
    groups=("count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)
_N_GOI_MOI_GOI = PackPattern(
    id="TIKI_N_GOI_MOI_GOI",
    regex=re.compile(
        r"(?i)(?P<count>\d+)\s*gói\b.{0,25}?mỗi\s*gói\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>gr|g|gam)\b"
    ),
    groups=("count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)

_COMBO_N_CASE_N = PackPattern(
    id="TIKI_COMBO_N_CASE_N",
    regex=re.compile(
        r"(?i)combo\s*(?P<count2>\d+)\s*thùng\s*(?P<count>\d+)\s*(?:hộp|chai|lon|gói|bịch)\b"
        r".*?(?<![\d.,])(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|l|kg|gr|g)\b"
    ),
    groups=("count2", "count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)

PATCH = SourcePatch(
    additions=(_CASE_N_LIT, _N_X_LIT, _N_GOI_MOI_GOI, _COMBO_N_CASE_N),
    intent={
        "TIKI_CASE_N_LIT": Intent(
            why="'Thùng/Combo/Lốc N hộp|chai ... V Lít' is N units of V litres",
            expect="volume -> volume",
            rows=25,
            examples=(
                "Thùng 12 hộp sữa tươi tiệt trùng TH True Milk  ít đường 1 Lít",
                "Thùng 8 Hộp Sữa Hạt Hạnh Nhân Australia's Own Hộp 1 Lít",
                "Combo 2 chai Dầu ăn Tân Sanh Chiên Giòn Thượng Hạng Chai 2 Lít",
                "Lốc 6 chai Bia chai tươi Việt Hà ( 1 lít/chai )",
            ),
        ),
        "TIKI_N_X_LIT": Intent(
            why="'(N hộp x V Lít)' is N units of V litres",
            expect="volume -> volume",
            rows=4,
            examples=(
                "Thùng Veyo sữa hạt 05 loại cao cấp (10 hộp x 1 Lít)",
                "Thùng Vinasoy Fami Green soy rất ít đường hộp (10 hộp x 1 Lít)",
            ),
        ),
        "TIKI_N_GOI_MOI_GOI": Intent(
            why="'N gói ... mỗi gói Xg' is N sachets of X grams each",
            expect="mass -> mass",
            rows=18,
            examples=(
                "Mua DMAXX thức uống bổ sung vitamin năng lượng không đường DAMODE 58 gói màu đỏ mỗi gói 2,2gr tại d&ghouse",
                "DMAXX thức uống bổ sung vitamin năng lượng có đường DAMODE 46 gói màu xanh mỗi gói 22gr",
                "DMAXX thức uống bổ sung vitamin năng lượng có đường DAMODE 90 gói màu xanh mỗi gói 22gr",
            ),
        ),
        "TIKI_COMBO_N_CASE_N": Intent(
            why="'Combo A Thùng B hộp ... V ml' is A x B units of V",
            expect="volume -> volume",
            rows=5,
            examples=(
                "[Tặng Balo MILO] Combo 2 Thùng 48 Hộp Sữa lúa mạch Nestlé MILO ít đường 180ml",
            ),
        ),
    },
)
