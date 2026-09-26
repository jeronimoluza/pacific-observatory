r"""hypermart: spelled-out "gram" / "kilogram" size words.

Same gap as pasar_segar/sayurbox: hypermart's catalogue is mostly ALL CAPS
and occasionally spells the size word out in full instead of using the
abbreviations in `units.yaml` -- "EDO MINIPAU CHEESE 200 GRAM", "MABELL
SPICY WING 500 GRAM", "VALUE PLUS ABON SAPI REGULER 1 KILOGRAM". "gram" is
missing entirely from units.yaml; "kilogram"/"kilo" (English) are too (the
vocab only has other languages' spelled kilo words: Thai กิโล, Hebrew קילו,
etc, plus the universal "kg" abbreviation).

Checked and dropped: hypermart also has spelled-out "liter" ("KARA COCONUT
OIL REF 2 LITER", "BIMOLI COOKING OIL KLASIK REFILL 2 LITER") -- same as
pasar_segar, `units.yaml` already lists liter/litre as volume surfaces, so
no liter pattern is added here.

Value is `\d+(?:,\d+)?` with a `(?<!\d)(?<!x )` lookbehind, same reasoning
as the pasar_segar/sayurbox patches: excludes a bare-dot thousands-grouped
size (none observed in this source's gap, kept as a standing rule) and a
"gram"/"kilogram" glued to an "x " multiplier (none observed here either,
kept for consistency and safety since hypermart is a large, varied
catalogue).

Measured 2026-09-26 with `rulecheck source hypermart` (hypermart is
indonesia-only): 3 rows item -> mass (gram), 1 row item -> mass (kilogram).
Small (hypermart's catalogue mostly already uses abbreviations), but clean
and zero-risk. Verdict: model_review.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_GRAM = PackPattern(
    id="HYPERMART_GRAM",
    regex=re.compile(r"(?<!\d)(?<!x )(?P<value>\d+(?:,\d+)?)\s*gram\b", re.IGNORECASE),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.001),
)

_KILOGRAM = PackPattern(
    id="HYPERMART_KILOGRAM",
    regex=re.compile(r"(?<!\d)(?<!x )(?P<value>\d+(?:,\d+)?)\s*kilo(?:gram)?\b", re.IGNORECASE),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=1.0),
)

PATCH = SourcePatch(
    additions=(_GRAM, _KILOGRAM),
    intent={
        "HYPERMART_GRAM": Intent(
            why="spelled-out 'gram' states the size in grams",
            expect="item -> mass",
            rows=3,
            examples=(
                "EDO MINIPAU CHEESE 200 GRAM",
                "MABELL SPICY WING 500 GRAM",
                "EDO MINIPAU SALTED CARAMEL 200 GRAM",
            ),
        ),
        "HYPERMART_KILOGRAM": Intent(
            why="spelled-out 'kilogram'/'kilo' states the size in kilograms",
            expect="item -> mass",
            rows=1,
            examples=(
                "VALUE PLUS ABON SAPI REGULER 1 KILOGRAM",
            ),
        ),
    },
)
