"""aeon_online: a size glued directly onto the preceding word, no space.

aeon_online's catalogue frequently glues the pack size straight onto the
preceding word with no separating space ("SUPER PURE HONEY1KG", "BERTOLLI
EXTRA VIRGIN500ML", "CS SPECIAL PIG EAR PATE500G", "FISH SAUCE TREY
KANCHANHCHRAS750ML", "TICKY COCOA22G", "ORGANIC GREEN LETTUCE200G"). The
shared VALUE_UNIT left guard (`_LB` in grammar.py) explicitly refuses a value
immediately preceded by a letter or digit -- by design, to keep it from
reading a SKU code glued to a preceding abbreviation ("Supppwdr1.6Kg", the
Philippines rose_pharmacy finding) as a size. For aeon_online this guard costs
real rows: the name carries a real, unambiguous size and nothing else, and the
row falls to item/NaN or (worse) an imputed_fit leaf default that silently
replaces the true value with the leaf's typical size.

This is the same extra_unit-style shape as makro_pro/tiki/farm2metro_ph: a
source-scoped PackPattern that relaxes the left guard for aeon_online only,
reusing the ALREADY-shared unit vocabulary (kg/gm/ml/g/l resolve through the
existing UNIT_NORM/UNIT_MAP table in unit_tables.py -- nothing added there),
without touching grammar.py's `_LB` guard itself.

The letter 'x'/'X' is excluded from the left guard on purpose: "24X250ML",
"20BAGSX40SX22G", "16X3X78G" are already read correctly by the existing
multipack (count x value-unit) patterns, and letting this new pattern also
fire there risks it winning first (source patterns go first in their bucket,
stage-b-extraction.md) and dropping the count. No true-miss example found in
the corpus has a digit immediately preceded by x/X, so excluding it costs
nothing (confirmed on the full aeon_online probe, 2026-09-26).

A trailing " X<N>" AFTER the unit is excluded the same way: "CHINESE MUSHROOMS
NOODLES1000G X15" and "YUXIANG WHEAT FLOUT1000G X15" are a case of 15 x 1000 g
and already read correctly (mass 1 kg, multiplier 15) by the existing
value-unit-x-count multipack pattern. First rulecheck run (2026-09-26, before
this lookahead) showed this pattern winning the same text span and dropping
the multiplier to 1 (count_lost on 3 names, 2 of them food) -- the same class
of mistake the Thailand pilot flagged ("a Sonnet found a shared-code bug but
copied it into its own patch"). The lookahead restores the multipack pattern's
priority on that shape.

Probed 2026-09-26 on the Stage B 01+02.1 snapshot (250 distinct aeon_online
names match this shape): 102 already resolve correctly through other patterns
(mostly the "NxV UNIT" multipack forms, left untouched here since 'x' is
excluded); 2 are pure misses (item/NaN despite a clean size, "ORGANIC GREEN
LETTUCE200G[, 1PCS]"); ~112 are wrong imputed_fit values silently replacing a
real, readable size with the leaf's typical default (e.g. "SUPER PURE
HONEY1KG" read as 0.5 kg, the honey leaf's default, instead of 1 kg; "TICKY
COCOA22G" read as 0.2 kg instead of 0.022 kg).

rulecheck source aeon_online (2026-09-26, verdict model_review, after the
trailing-X<N> lookahead above): 1,025 rows across 247 distinct names, 0 count
lost, transitions item->mass 600, item->volume 412, volume->volume 13. All 96
distinct food rows hand-read correct (real sizes, right unit). The 40 non-food
(coicop_code=None) names sampled include ~8 genuine false positives -- SKU or
model codes ending in a digit that happens to look like a unit ("TV126AM1233G"
read as 1.233 kg; "L-R40L Solex Lock 40MM" read as 40 L from the "R40L" model
code; "TMFM3BS007CWA11G" read as 11 g). These rows have coicop_code=None, so
Stage B never sees them (extraction reads only 01/02.1 rows, stage-b-
extraction.md item 1) -- harmless to trust, but noted here since rulecheck
scores every source row, all divisions, not just 01/02.1.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_AEON_GLUED = PackPattern(
    id="AEON_GLUED_UNIT",
    regex=re.compile(
        r"(?<=[A-Za-z])(?<![Xx])(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|gm|ml|g|l)\b"
        r"(?!\s*[xX]\s*\d)",
        re.IGNORECASE,
    ),
    groups=("value", "unit"),
    lang="any",
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)

PATCH = SourcePatch(
    additions=(_AEON_GLUED,),
    intent={
        "AEON_GLUED_UNIT": Intent(
            why="aeon_online glues the pack size onto the preceding word with no space",
            expect="item -> mass, item -> volume, mass -> mass, volume -> volume, "
            "count -> mass, count -> volume",
            rows=1025,
            examples=(
                "SUPER PURE HONEY1KG",
                "BERTOLLI EXTRA VIRGIN500ML",
                "CS SPECIAL PIG EAR PATE500G",
                "FISH SAUCE TREY KANCHANHCHRAS750ML",
                "TICKY COCOA22G",
                "ORGANIC GREEN LETTUCE200G",
                "KELLOGG`S FROOT LOOPS300G",
                "OLIVE BLENDING OIL2L",
            ),
            count_loss=True,
        ),
    },
)
