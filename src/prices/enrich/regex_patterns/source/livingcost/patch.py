"""livingcost: "Cappuccino" is one cup.

The name carries no size, so Stage B imputed the coffee leaf's mode -- a
10-sachet box -- and priced a cafe cup at a tenth (465 New Zealand rows trusted
at 1/10 the unit value). One cup is count 1. It is a restaurant item filed
under coffee (classify, frozen); as count 1 it lands in its own per-piece cell
instead of beside sachet boxes.

Measured 2026-09-26: the only sizeless livingcost name in 01 + 02.1 in New
Zealand and Vietnam; 499 product rows (one per city), 30 countries.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_CUP = PackPattern(
    id="LIVINGCOST_CAPPUCCINO_CUP",
    regex=re.compile(r"(?i)^\s*cappuccino\s*$"),
    groups=(),
    pricing_basis_emit="count",
    lang="any",
    role="extract",
    kind="pricing_basis_marker",
    bucket="per_unit_marker",
)

PATCH = SourcePatch(
    additions=(_CUP,),
    intent={
        "LIVINGCOST_CAPPUCCINO_CUP": Intent(
            why="'Cappuccino' is one cup, not a box of sachets",
            expect="item -> count",
            rows=499,
            examples=("Cappuccino",),
        ),
    },
)
