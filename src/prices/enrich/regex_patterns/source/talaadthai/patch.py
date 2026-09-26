"""talaadthai: "กล่อง N ลูก" is a box of N pieces, not a 1 kg item.

talaadthai (Thai wholesale produce market) sells imported fruit by the box,
naming the box count as "กล่อง N ลูก" (box of N pieces), sometimes as a range
("กล่อง 100 – 125 ลูก"). No per-piece weight is ever given. The shared regex
has no per-unit weight to find, so the row is left sizeless (item/NaN) at
extraction and later gets an imputed 1 kg mass at Stage B trust, which is
wildly wrong for a box of 18-216 apples/kiwi/persimmon and lands it in
review_uv_out on an absurd implied per-kg price.

Reading "กล่อง N ลูก" as count=N instead turns the row into a count-basis price
(price per box / N pieces = price per piece), which is a materially more
correct statement of what is being sold even where the leaf's basis map does
not allow count for apples (then it correctly lands in review_basis instead of
a bogus mass outlier).

A range takes the lower bound only ("กล่อง 100 – 125 ลูก" -> count=100), same
convention as the shared range_lower.py rule elsewhere in the tree.

extra_count mechanism (same shape as the shared count-noun patterns in
regex_patterns/buckets/count_pack/): a source-local regex that emits a `count`
group, scoped to talaadthai only.

Measured 2026-09-26 with `rulecheck source talaadthai` (verdict model_review):
43 rows move (35 item -> count, 6 mass -> count where a bogus imputed 1 kg had
already been assigned, e.g. "ส้มซันควิก ออสเตรเลีย กล่อง 64 - 72 ลูก" mass=1.0
-> count=64). 2 more rows keep pricing_basis="mass" unchanged (mass -> mass):
these boxes also state an explicit total weight in parentheses ("กล่อง14 - 15
ลูก (8 กก.)"), which the shared regex already reads correctly as 8 kg; this
patch only adds the piece count (14) alongside it, useful for the review_piece
implied-weight check, without disturbing the already-correct mass. Hand-read
every changed row (all 43 are food, all imported fruit) -- no false positives.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_BOX_N_PIECES = PackPattern(
    id="TALAADTHAI_BOX_N_PIECES",
    regex=re.compile(r"กล่อง\s*(?P<count>\d+)\s*(?:[-–—]\s*\d+\s*)?ลูก"),
    groups=("count",),
    lang="any",
    role="extract",
    kind="extra_count",
    bucket="count_pack",
)

PATCH = SourcePatch(
    additions=(_BOX_N_PIECES,),
    intent={
        "TALAADTHAI_BOX_N_PIECES": Intent(
            why="talaadthai: 'กล่อง N ลูก' (box of N pieces) is a piece count, not a 1 kg item",
            expect="item -> count, mass -> count, mass -> mass",
            rows=43,
            examples=(
                "แอปเปิ้ลฟูจิ นิวซีแลนด์ – กล่อง 110 ลูก",
                "แอปเปิ้ลฟูจิ เซาท์แอฟริกา – กล่อง 100 – 125 ลูก",
                "แอปเปิ้ลกาล่า อเมริกา – กล่อง100 – 120 ลูก",
                "กีวี ฝรั่งเศส – กล่อง 33 ลูก",
                "แอปเปิ้ลฟูจิยักษ์ ญี่ปุ่น – กล่อง 18 ลูก",
            ),
        ),
    },
)
