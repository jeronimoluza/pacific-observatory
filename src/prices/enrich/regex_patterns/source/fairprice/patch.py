"""fairprice: an explicit trailing ", N g." size loses to a false "Stage <n> CC" read.

fairprice's "Happy Family" baby-food line names the product stage inline
("Happy Family Stage 2 CC - Apples Pumpkin & Carrots, 113 g."), and the shared
VALUE_UNIT regex reads "2 CC" (the stage number followed by the SKU-code
suffix "CC") as 2 cubic centimetres before it ever reaches the real, explicit
"113 g." at the end of the string. "cc" is a legitimate shared unit surface
(cubic centimetre, units.yaml) used correctly elsewhere (e.g. Japanese
"300cc" bottles), so this is not a shared-grammar bug -- it is this one
source's naming convention colliding with a generic unit token. The result:
volume 0.002 lt instead of mass 0.113 kg, landing in review_basis (the leaf,
baby-food purees, only allows mass).

This canon pattern fires only when "stage <n> cc" appears (the exact brand
collision) AND the name ends in an explicit "N g" / "N g.": it reads that
trailing gram value (with a literal "g" unit group) as mass, straight out of
`extract_pack`'s own pack_lang pass. It has to be a `kind="canon"` pattern
feeding `ps.pack`, not an `extra_unit` fallback: `extra_unit` only fills in
when nothing else found a value, but here the shared grammar's secondary
value+unit scan (`_find_value_unit_anywhere` / Pass 1d in `extract_decide.py`)
already succeeds on "2 CC" earlier in the string, so an `extra_unit` entry
never gets consulted (tried and measured 0 rows moved). A source addition to
`ps.pack` runs first in `extract_pack`'s pattern list, wins before the
secondary scan is ever reached, and sets pack_value/pack_unit directly.

It is scoped to the "stage ... cc" trigger rather than a bare trailing-gram
catch-all, because a generic trailing-gram pattern would duplicate the shared
grammar's already-correct behaviour on hundreds of other fairprice names
(spices, dips, sausages: "Simply Organic Basil, 15g", "Santa Maria Dip Nachos
Cheese Style, 250G") for no benefit and unnecessary surface area.

Measured 2026-09-26 on `observations.parquet` (singapore, 01+02.1, current
snapshot): 7 distinct names, all "Happy Family Stage 2 CC ...", all baby food
(coicop 01.1.9.2.3). `rulecheck source fairprice` measures the full-history
row count (below).
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_STAGE_CC_TRAILING_G = PackPattern(
    id="FAIRPRICE_STAGE_CC_TRAILING_G",
    regex=re.compile(
        r"(?i)stage\s*\d+\s*cc\b.*?(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>g)\.?\s*$"
    ),
    groups=("value", "unit"),
    lang="any",
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)

PATCH = SourcePatch(
    additions=(_STAGE_CC_TRAILING_G,),
    intent={
        "FAIRPRICE_STAGE_CC_TRAILING_G": Intent(
            why="'Stage N CC ... , M g.' has a real trailing gram size; it must "
            "win over the false 'N CC' (cubic centimetre) read earlier in the name",
            expect="volume -> mass",
            rows=7,
            examples=(
                "Happy Family Stage 2 CC - Apples Pumpkin & Carrots, 113 g.",
                "Happy Family Stage 2 CC - Apples Blueberries & Oats, 113 g.",
                "Happy Family Stage 2 CC - Bananas Raspberries & Oats, 113 g.",
                "Happy Family Stage 2 CC - Pears Zucchini & Peas, 113 g.",
                "Happy Family Stage 2 CC - Apples Kale & Avocadoes, 113 g.",
                "Happy Family Stage 2 CC - Bananas Sweet Potatoes &Papaya 113g",
                "Happy Family Stage 2 CC - Green Beans Spinach & Pears, 113 g.",
            ),
        ),
    },
)
