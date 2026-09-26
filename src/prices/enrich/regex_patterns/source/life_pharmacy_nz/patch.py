"""life_pharmacy_nz: "<V>g Npk" is N sachets of V grams, not a pack total.

The pharmacy writes the per-sachet size before the count ("LittleOak Formula
Sach 30g 6pk" at NZD 15.95 is six 30 g sachets), so the shared reading -- the
count inert beside the measure -- priced the box as one sachet, 6x too dear.
Woolworths NZ uses the same shape for the pack TOTAL ("fish fingers 375g
15pack"), and bargain_chemist mixes both, so neither is patched.

A canon pattern, not the `piece_is_case` flag: the flag also multiplied tablet
doses ("Vit C 1200mg Tablets 60s"), and rulecheck refused it. Only g/ml and
"pk" match, so mg doses and "30s" counts are left alone.

Measured 2026-09-26 on the New Zealand Stage B pilot: 30 names (8 food), all one item per count (sachets, masks, soaps).
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_G_NPK = PackPattern(
    id="LIFE_PHARMACY_G_NPK",
    regex=re.compile(r"(?i)(?<![\d.])(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>g|ml)\s+(?P<count>\d+)\s*pk\b"),
    groups=("count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)

PATCH = SourcePatch(
    additions=(_G_NPK,),
    intent={
        "LIFE_PHARMACY_G_NPK": Intent(
            why="pharmacy: '<V>g Npk' is N sachets of V grams",
            expect="mass -> mass",
            rows=30,
            examples=(
                "LittleOak Infant Formula Sach 30g 6pk",
                "BioSlim VLCD Shake Classic Chocolate 46g 18pk",
                "The Lady Shake Restore Chocolate 50g 10pk",
            ),
        ),
    },
)
