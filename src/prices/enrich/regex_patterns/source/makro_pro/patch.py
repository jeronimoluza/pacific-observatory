"""makro_pro: a bare "N ล." is litres, not glued into a longer word.

2026-09-27: the gram half ("N ก.", MAKRO_G_ABBR) moved to the shared rewrite
`regex_patterns/shared/thai_gram.py`: lotuss_th and gourmet_market_th write it
too, and as an extra_unit it dropped the case count of "400 ก. X 20". The
history below is kept as measured.

makro_pro (Thai wholesale cash-and-carry) abbreviates กรัม (gram) and ลิตร
(litre) as a bare "ก." / "ล." with a mandatory period ("บลูเบอร์รี่ 500 ก.",
"เอโร่ น้ํามันถั่วเหลือง 5 ล."). units.yaml's Thai surfaces only spell out the
full words (กรัม, กิโลกรัม, กก, มล, ลิตร), so these rows never match VALUE_UNIT
and fall to item/NaN (unsized), then get an imputed size at Stage B trust.

Thai script has no inter-word spaces, so a bare "ก"/"ล" risks reading as the
first letter of a longer word ("กรัม", "กิโล", "กก" all start with the same
letter; "ลิตร" starts with ล). Python's `\\b` already refuses to fire between
two Thai letters (both are \\w, so there is no boundary inside "กรัม"), but the
mandatory period plus a negative lookahead against a following Thai letter
(`[\\u0E01-\\u0E4F]`: consonants, vowels, tone marks) is kept as an explicit
second guard rather than relying on that alone. The no-period form ("350 ก 1")
is deliberately left unpatched: without the period it is ambiguous with a
following count/serial number.

extra_unit mechanism (same shape as the shared CENTILITRE/LITRE_VI patterns in
regex_patterns/vocab/pack_basis.yaml): a source-local regex that emits its own
value+unit via `unit_emit`, scoped to makro_pro only, without touching
units.yaml or VALUE_UNIT.

Measured 2026-09-26 with `rulecheck source makro_pro` (verdict model_review):
MAKRO_G_ABBR moves 7,958 rows (item -> mass 7,956; plus 2 rows where a WORSE
prior parse is replaced, see below), MAKRO_L_ABBR moves 1,514 rows (item ->
volume 1,513; plus 1). This is larger than the 01+02.1-only, current-snapshot
estimate (207 / 21 "item"-basis rows) because rulecheck measures every makro_pro
product row, all categories, all history.

Two rows lose a count and two land on an undeclared transition, all genuine
fixes over a worse prior read, hand-checked against `changed.parquet`:
- "...โจ๊ก...75ก. สําหรับเด็ก 6 M+" (baby porridge, 75 g): was count=6, misread
  from "6 M+" (6 months+, an age label) as a count; now correctly mass=0.075.
- "...บดแช่แข็ง 85CL 500 ก." (frozen minced beef): was volume=0.85 (the shared
  CENTILITRE pattern misreading "85CL" as 85 cl); now correctly mass=0.5 from
  "500 ก.".
- "ชาร์ป กระติกน้ําร้อน 1.8 ล. รุ่น Kp-19S..." (non-food: an electric thermos):
  was count=19, misread from the model number "Kp-19S"; now correctly
  volume=1.8 from "1.8 ล.". count_loss, declared below.
No false positives found in a manual read of 25 sampled non-food changed rows
(cosmetics, toothpaste, supplements, cookware all correctly sized) plus every
food row in the 3 undeclared-transition set.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

# Thai consonants/vowels/tone marks: a following one means this is the start of
# a longer word (กรัม, กิโล, กก, ...), not the bare abbreviation.
_TH_CONT = "ก-๏"

_L_ABBR = PackPattern(
    id="MAKRO_L_ABBR",
    regex=re.compile(rf"(?<![A-Za-z0-9.,])(?P<value>\d+(?:\.\d+)?)\s*ล\.(?![{_TH_CONT}])"),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="volume", su="lt", mul=1.0),
)

PATCH = SourcePatch(
    additions=(_L_ABBR,),
    intent={
        "MAKRO_L_ABBR": Intent(
            why="makro_pro abbreviates ลิตร (litre) as a bare 'ล.' with a period",
            expect="item -> volume, count -> volume",
            rows=1514,
            examples=(
                "เอโร่ น้ํามันถั่วเหลือง 5 ล.",
                "เอ็มมิลค์ นมไม่มีแลคโตสไขมันต่ํา 1 ล.",
                "เอโร่ น้ํามันถั่วเหลือง 13.75 ล.",
                "ชาร์ป กระติกน้ําร้อน 1.8 ล. รุ่น Kp-19S คละสี/คละลาย",
            ),
            count_loss=True,
        ),
    },
)
