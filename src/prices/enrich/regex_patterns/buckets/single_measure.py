"""Single value+unit bucket — the canon mass/volume pair + extra-unit fall-throughs.

Records moved VERBATIM from shared/value_unit.py, lang/zh/volume_mass.py (canon)
and shared/extra_units.py (extra_unit), ids renamed to SCREAMING_SNAKE.
Declaration order: VALUE_UNIT, VALUE_UNIT_ZH (canon → canon tail, since multipack
precedes this module in MODULE_ORDER), then CENTILITRE, LITRE_VI (extra_unit →
GOLDEN_EXTRA_UNITS). VALUE_UNIT keeps suppress_window=20 verbatim (BUG 3 / BUG 4,
load-bearing).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern, UnitEmit

# BUG 3 / BUG 4 (wired 2026-06-23): appliance-capacity ("99L freezer") and
# apparel fabric-weight ("5.6oz t-shirt") false mass/volume extraction.
# `suppress_window` below is consumed by extract.py: when a value+unit match sits
# within `suppress_window` chars of an appliance / apparel / storage cue, the
# number is the product's CAPACITY or FABRIC WEIGHT, not a sale quantity, so the
# mass/volume emit is dropped and the row falls through to item.

PATTERNS: tuple[PackPattern, ...] = (
    # "500g", "1L", "135ml", "158GM", "60gr", "25mg", "1ltr", "5LT", "2.25LTRS"
    # spelled-out liters|litres|liter|litre + ltrs|ltr|lt placed before l|L so the
    # longest litre spelling wins (IGNORECASE) — full word avoids matching the bare
    # "lit" prefix of lithium/little/litchi.
    # value also accepts a leading-dot decimal (".3 mL", ".75 L" — pharma dosing);
    # the left lookbehind still rejects a dot glued to a letter/digit ("No.3 ml").
    PackPattern(
        id="VALUE_UNIT",
        regex=re.compile(
            r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?|[.,]\d+)\s*(?P<unit>ml|mL|ML|liters|litres|liter|litre|ltrs|ltr|lt|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB|Oz)\b",
            re.IGNORECASE,
        ),
        groups=("value", "unit"),
        suppress_window=20,
        lang="any",
        role="canonicalization",
        kind="canon",
        bucket="single_measure",
    ),
    # "500毫升" "1公升" "200公克" "2公斤" "50克"
    PackPattern(
        id="VALUE_UNIT_ZH",
        regex=re.compile(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>公升|毫升|公斤|公克|克|升)",
            re.IGNORECASE,
        ),
        groups=("value", "unit"),
        lang="zh",
        role="canonicalization",
        kind="canon",
        bucket="single_measure",
    ),
    PackPattern(
        id="CENTILITRE",
        regex=re.compile(
            r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?)\s*(?:cl|CL|cL|Cl)\b",
        ),
        groups=("value",),
        lang="any",
        role="extract",
        unit_emit=UnitEmit(basis="volume", su="lt", mul=0.01),
        kind="extra_unit",
        bucket="single_measure",
    ),
    PackPattern(
        id="LITRE_VI",
        regex=re.compile(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*l[íi]t",
        ),
        groups=("value",),
        lang="any",
        role="extract",
        unit_emit=UnitEmit(basis="volume", su="lt", mul=1.0),
        kind="extra_unit",
        bucket="single_measure",
    ),
)
