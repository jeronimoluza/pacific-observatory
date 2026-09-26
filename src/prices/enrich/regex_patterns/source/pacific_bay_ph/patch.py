"""pacific_bay_ph: a trailing "(<N> grams)" / "(<N> kilo(s))" is the pack size.

The site puts the size in parentheses at the end of the name: "Andouille
Sausage (500 grams)", "Alaskan Pollock Fillet (1 kilo)", "Broccoli Florets
(1 kilo)". Plain "(1 kg)" already extracts (kg is in the shared vocab); only
the spelled-out "gram(s)"/"kilo(s)" surface is missing there, same gap as
farm2metro_ph and the New Zealand pilot's "500 grams" note. Scoped here, not a
units.yaml edit -- see the report's shared-fix proposal.

Range sizes -- "(500-600 grams)", "(300-350 grams)", "(0.9 to 1.35 kilos)",
"(1.1-1.3kgs)" -- do NOT match either pattern (the value group requires the
unit word right after the number, and a range has another number first), so
they stay in review rather than guess a bound. That is intended, not a gap in
this patch.

Measured 2026-09-26 on products_input (pacific_bay_ph is philippines-only):
rulecheck gives the exact row count.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_PAREN_GRAMS = PackPattern(
    id="PACIFIC_BAY_PAREN_GRAMS",
    regex=re.compile(r"(?i)\(\s*(?P<value>\d+(?:\.\d+)?)\s*grams?\s*\)"),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.001),
)

_PAREN_KILOS = PackPattern(
    id="PACIFIC_BAY_PAREN_KILOS",
    regex=re.compile(r"(?i)\(\s*(?P<value>\d+(?:\.\d+)?)\s*kilo(?:gram)?s?\s*\)"),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=1.0),
)

PATCH = SourcePatch(
    additions=(_PAREN_GRAMS, _PAREN_KILOS),
    intent={
        "PACIFIC_BAY_PAREN_GRAMS": Intent(
            why="trailing '(<N> grams)' states the pack size in grams",
            expect="item -> mass",
            rows=273,
            examples=(
                "A1 Original Steak Sauce (283 grams)",
                "Andouille Sausage (500 grams)",
                "Ardo Bio Organic Broccoli Florets (600 grams)",
                "Brie (125 grams)",
                "Bangus Fish Nuggets (200 grams)",
            ),
        ),
        "PACIFIC_BAY_PAREN_KILOS": Intent(
            why="trailing '(<N> kilo(s))' states the pack size in kilos",
            expect="item -> mass",
            rows=56,
            examples=(
                "Alaskan Pollock Fillet (1 kilo)",
                "Ardo Baby Carrots (1 kilo)",
                "Baby Squid (1 kilo)",
                "Beef Shank (1 kilo)",
                "Broccoli Florets (1 kilo)",
            ),
        ),
    },
)
