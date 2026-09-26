"""horizon_farms: "(N Eggs)" states an exact egg count.

English "eggs" is not a count noun in the shared library (same gap as
expatistan's "12 eggs, large"). Without it, these rows are sizeless and Stage B
imputes the leaf's fitted mode (36 -- coincidentally close to some real packs,
never trusted since size_source=imputed_fit). The count is stated in parens;
read it. Ranges ("12-30 Eggs", "10-40 Eggs") are left alone: no single count is
stated, and guessing one would not be a measured fact.

Measured 2026-09-26 on horizon_farms (japan only): 224 rows, 3 product names
("(12 Eggs)" x2 names, "(20 Eggs)" x1 name). 0 rows lose a count.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_EGGS = PackPattern(
    id="HORIZON_FARMS_N_EGGS",
    regex=re.compile(r"(?i)\((?P<count>\d+)\s+Eggs\)"),
    groups=("count",),
    lang="any",
    role="extract",
    kind="extra_count",
    bucket="count_pack",
)

PATCH = SourcePatch(
    additions=(_EGGS,),
    intent={
        "HORIZON_FARMS_N_EGGS": Intent(
            why="'(12 Eggs)' / '(20 Eggs)' states an exact count",
            expect="item -> count",
            rows=224,
            examples=(
                "Real Free-Range Raw Eggs from Japan (12 Eggs) (Terms & Conditions Apply)",
                "Certified Organic Free-Range Eggs from Japan (12 Eggs) (Terms & Conditions Apply)",
                "Real Range-Free Eggs from Japan (20 Eggs) (¥1,150 Shipping)",
            ),
        ),
    },
)
