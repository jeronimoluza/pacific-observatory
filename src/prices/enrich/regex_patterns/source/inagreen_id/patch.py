r"""inagreen_id: spelled-out "Gram" size word.

Same gap as pasar_segar/sayurbox/hypermart/nutrimart_id: "Inagreen Farm
Bandung Kunyit / Kunir 100 Gram", "INAGRAIN Organic Black Chia Seeds 200
Gram". units.yaml has no "gram" surface.

Value is `\d+(?:,\d+)?` with a `(?<!\d)(?<!x )` lookbehind, same reasoning
as the other patches in this country (bare-dot thousands-grouping and an
"x N" multiplier prefix are both excluded; neither shape was observed in
this source's gap, kept as a standing rule).

Measured 2026-09-26 with `rulecheck source inagreen_id` (inagreen_id is
indonesia-only): 111 rows item -> mass, 0 count_loss. Verdict: model_review.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_GRAM = PackPattern(
    id="INAGREEN_ID_GRAM",
    regex=re.compile(r"(?<![\d.,])(?<!x )(?P<value>\d+(?:,\d+)?)\s*gram\b", re.IGNORECASE),
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
        "INAGREEN_ID_GRAM": Intent(
            why="spelled-out 'gram' states the size in grams",
            expect="item -> mass",
            rows=111,
            examples=(
                "Inagreen Farm Bandung Kunyit / Kunir 100 Gram",
                "Inagreen Farm Bandung Tarragon Herbs Fresh 50 Gram",
                "Inagreen Farm Bandung Cabe Hijau Besar Tanjung 250 Gram",
                "Inagreen Farm Bandung Daun Kemangi 100 Gram",
                "INAGRAIN Organic Black Chia Seeds 200 Gram",
            ),
        ),
    },
)
