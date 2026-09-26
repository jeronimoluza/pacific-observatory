"""bargain_chemist: two multipack shapes the shared "count precedes measure
= total" convention gets backwards.

1. "<V>g Npk" (measure then count, glued, no "Pack" word): the pharmacy
   convention is one item per count, same as unichem_nz / life_pharmacy_nz's
   patch for the identical shape ("Optislim VLCD CappCrnch Bar 60g 5pk" is
   five 60 g bars, not one). Copied here rather than shared because the same
   shape means the PACK TOTAL elsewhere at this same source (see item 2, and
   the unichem_nz patch's own note that bargain_chemist mixes both and so
   neither the shared code nor a single flag can carry it). Grams only, not
   ml: the only ml candidate in the catalogue is a syringe dose ("SYRINGE
   INS. U/F BD 31G 0.3ML 10pk") where the regex would grab the wrong measure
   (0.3 mL instead of 31 G) and flip the basis; there is no genuine ml-based
   "Vml Npk" food row here (Shake2Go's "350ml 4pk" is already read correctly
   by the shared volume-pack default, no patch needed).

2. "N Pack Vg Sachets" (count precedes measure, the shared convention's
   assumed-total order): the trailing "Sachet(s)" word marks V as the
   PER-SACHET size, not the total ("OPTIFAST VLCD Shake Vanilla - 18 Pack
   53g Sachets" is 18 x 53 g = 954 g, not 53 g). Confirmed against the same
   product line sold with an explicit stated total ("OPTIFAST VLCD Shake
   Caramel Flavour 12 Pack 636g" = 12 x 53 g), so both spellings resolve to
   the same per-sachet size. Without this, the row priced the whole box at
   one sachet's weight (54.99 / 0.053 kg = NZD 1,038/kg, flagged
   review_uv_implausible) instead of the correct ~58-73/kg range.

Both are single canon patterns (count+value+unit captured together) so the
shared `_rung_pack_unit_emit` reads the count as `pack_count` and promotes it
straight to `multiplier`, the same route `_rung_pack_unit_emit` already takes
for volume packs -- no shared file is touched.

Measured 2026-09-26 with `rulecheck source bargain_chemist` (full bargain_chemist
catalogue, not just the Stage B 01/02.1 slice): pattern 2 (sachets) 15 rows,
food (VLCD shakes, soup, dessert); pattern 1 (g Npk) 33 rows, mostly non-food
toiletry multipacks (soap bars, lip balm, hand cream) plus the food Optislim
bar -- all mass -> mass, all a pack of N same-size items, verdict model_review.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_G_NPK = PackPattern(
    id="BARGAIN_G_NPK",
    regex=re.compile(r"(?i)(?<![\d.])(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>g)\s+(?P<count>\d+)\s*pk\b"),
    groups=("count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)

_N_PACK_SACHETS = PackPattern(
    id="BARGAIN_N_PACK_SACHETS",
    regex=re.compile(
        r"(?i)(?<!\d)(?P<count>\d+)\s*pack\s+(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>g|ml)\s*sachets?\b"
    ),
    groups=("count", "value", "unit"),
    role="canonicalization",
    kind="canon",
    bucket="multipack",
)

PATCH = SourcePatch(
    additions=(_N_PACK_SACHETS, _G_NPK),
    intent={
        "BARGAIN_N_PACK_SACHETS": Intent(
            why="'N Pack Vg Sachets' states the per-sachet size, not the pack total",
            expect="mass -> mass",
            rows=15,
            examples=(
                "OPTIFAST VLCD Shake Vanilla - 18 Pack 53g Sachets",
                "Optifast VLCD Shake Chocolate - 12 Pack 53g Sachets",
                "Optifast VLCD Shakes Asst Pack - 10 Pack 53g Sachets",
                "Optifast VLCD Soup Vegetable - 8 Pack 53g Sachets",
                "Optifast VLCD Shake Coffee - 12 Pack 53g Sachets",
                "Optifast VLCD Dessert Chocolate - 8 Pack 53g Sachets",
            ),
        ),
        "BARGAIN_G_NPK": Intent(
            why="'<V>g Npk' is N items of V grams (a pack of N same-size units), same shape as unichem_nz",
            expect="mass -> mass",
            rows=33,
            examples=(
                "Optislim VLCD CappCrnch Bar 60g 5pk",
                "DOVE Soap Go Fresh 100g 4pk",
                "FIORENTINO Soap LOTV 125g 3pk",
                "PALMOLIVE Nat DC Alm Milk Sp 90g 4pk",
                "SENCE Sensitive Lip Balm 4.3g 2pk",
            ),
        ),
    },
)
