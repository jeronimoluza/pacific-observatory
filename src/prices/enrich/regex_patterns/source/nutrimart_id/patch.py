r"""nutrimart_id: spelled-out "gram" size word.

Same gap as pasar_segar/sayurbox/hypermart: "Hilo Teen Korean Banana 250
gram - Susu Tinggi Kalsium Rendah Lemak", "Tropicana Slim Peanut Almond
Butter 300 gram -12 BOTOL". units.yaml has no "gram" surface.

Value is `\d+(?:,\d+)?` with `(?<!\d)(?<!x )` before it and `(?!\s*[-x]\s*\d)`
after "gram", on top of the pasar_segar/sayurbox lookbehinds. nutrimart_id's
own catalogue glues a CASE multiplier straight onto the gram size, either
trailing ("300 Gram x 2 pcs", "400 gram - 12BAG", "500 gram -12 BAG") or as
a leading "Twin Pack -" (one name only: "Twin Pack - Tropicana Slim Bumbu
Kaldu Ayam dan Jamur 100 gram"). The trailing lookahead excludes the first
shape entirely (left as `item`, unchanged, rather than reporting the
per-unit weight as the item's total mass -- the multiplier can be 2 or 12,
not always inert). The "Twin Pack" prefix is not practically excludable
with a fixed-width regex (no variable-length lookbehind in `re`) and is
accepted as a declared count_loss: 1 row reads 0.1 kg where the true pack
total is 0.2 kg, a real but rare (1 of 34) understatement rather than a
silent one -- a 2x unit-value shift on a food row is exactly what
rulecheck's uv_flag / model review is for.

Measured 2026-09-26 with `rulecheck source nutrimart_id` (nutrimart_id is
indonesia-only): 16 rows item -> mass, 1 row count -> mass (the accepted
Twin Pack case, count_loss). Verdict: model_review.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_GRAM = PackPattern(
    id="NUTRIMART_ID_GRAM",
    regex=re.compile(
        r"(?<![\d.,])(?<!x )(?P<value>\d+(?:,\d+)?)\s*gram\b(?!\s*[-x]\s*\d)", re.IGNORECASE
    ),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.001),
)

PATCH = SourcePatch(
    additions=(_GRAM,),
    intent={
        "NUTRIMART_ID_GRAM": Intent(
            why="spelled-out 'gram' states the size in grams",
            expect="item -> mass, count -> mass",
            rows=17,
            examples=(
                "Hilo Teen Korean Banana 250 gram - Susu Tinggi Kalsium Rendah Lemak",
                "Tropicana Slim Bumbu Kaldu Ayam Jamur 100 gram",
                "Tropicana Slim Peanut Almond Butter 300 gram",
                "Tropicana Slim Susu Low Fat Macchiato Coffee 500 gram",
            ),
            count_loss=True,
        ),
    },
)
