"""harris_farm_markets: a bare trailing "x<N>" is a piece count, not part of
the product name.

The source names multi-item bakery and grocery packs with a trailing "x<N>"
and no unit word at all ("Harris Farm Bread Rolls Wholemeal x6", "Boundary
Road Brioche Burger Buns x4", "Redbrick Coffee Pods x10"): no per-item weight
is ever given, so the shared regex finds no measure and the row is sizeless
(item/NaN) at extraction. Stage B then imputes the leaf's fitted mode
(size_source=imputed_fit, permanently excluded from trust) instead of reading
the count that is right there in the name.

Reading "x<N>" as count=N is materially correct for these leaves: bread
(01.1.1.3.1) and other bakery products (01.1.1.3.9) both allow a count basis
in the map ("rolls and tortillas / muffins, croissants sold in piece packs"),
as does coffee (01.2.2.0.1, "capsules/sachets by count"). Where the leaf is
mass-only (01.1.9.4.0 herbs/spices: "Fresh Herbs Parsley Continental x6
Bunches"), the row still correctly lands in review_basis instead of a bogus
imputed mass -- a materially more honest state, never worse than today.

First cut (a plain ``x`` + digits, anywhere) matched 1030 rows and was refused
by rulecheck: the count-promotion machinery in extract_decide.py (rung 3)
combines ANY extra_count candidate with a measure found ANYWHERE ELSE in the
name, so a loose "x<N>" quietly re-multiplied hundreds of already-correctly-
sized rows ("mass -> mass" 812 times) across the whole catalogue, not just the
sizeless ones this patch targets. Second cut (anchored to end-of-string, no
mass/volume unit word earlier) still let two non-food rows collide with an
EARLIER, already-correct count noun ("icare Eco Toilet Tissue Paper 3 Ply 180
Sheets x8": the real count is 180 sheets, "x8" rolls-per-case, and the new
pattern overwrote 180 with 8 -- an undeclared "count -> count" refusal). The
regex is therefore anchored twice: "x<N>" must be the LAST token in the name
(optionally followed by "Pack(s)"/"Bunch(es)"), AND no digit of any kind may
appear anywhere earlier in the string -- the exact shape of the sizeless names
below, nothing else, and by construction never a second number to collide
with. "Lincoln Bakery Sweet Pastry Shells x12 60mm" (a trailing diameter),
"Pirovic Free Range Eggs x12 660g" (a real total-mass measure follows) and
"...3 Ply 180 Sheets x8" (an earlier count) are all correctly excluded.

Measured 2026-09-26 with `rulecheck source harris_farm_markets`: rows and
verdict recorded in intent below. Hand-read every changed row: all food or
plausible grocery items, no false positives from dimension strings.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_X_COUNT = PackPattern(
    id="HARRIS_FARM_X_COUNT",
    regex=re.compile(
        r"(?i)^(?:(?!\d).)*?"
        r"\bx\s*(?P<count>\d+)\b\s*(?:Pack|Packs|Bunch|Bunches)?\s*$"
    ),
    groups=("count",),
    lang="any",
    role="extract",
    kind="extra_count",
    bucket="count_pack",
)

PATCH = SourcePatch(
    additions=(_X_COUNT,),
    intent={
        "HARRIS_FARM_X_COUNT": Intent(
            why="a bare trailing 'x<N>' (no unit) states a piece count",
            expect="item -> count",
            rows=181,
            examples=(
                "Harris Farm Bread Rolls Wholemeal x6",
                "Boundary Road Brioche Burger Buns x4",
                "Redbrick Coffee Pods x10",
                "Peace Bakery Lebanese Bread x7",
                "Fresh Herbs Parsley Continental x6 Bunches",
            ),
        ),
    },
)
