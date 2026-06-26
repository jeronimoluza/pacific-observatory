"""Single value+unit pattern (the common case) — canonicalization role."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

# BUG 3 / BUG 4 (wired 2026-06-23): appliance-capacity ("99L freezer") and
# apparel fabric-weight ("5.6oz t-shirt") false mass/volume extraction.
# `suppress_window` below is now consumed by extract.py: when a value+unit match
# sits within `suppress_window` chars of an appliance / apparel / storage cue
# (`_VU_SUPPRESS_CTX_RE` in extract.py), the number is the product's CAPACITY or
# FABRIC WEIGHT, not a sale quantity, so the mass/volume emit is dropped and the
# row falls through to item (or count, if a real pack count remains).

PATTERNS: tuple[PackPattern, ...] = (
    # "500g", "1L", "135ml", "158GM", "60gr", "25mg", "1ltr", "5LT", "2.25LTRS"
    # spelled-out liters|litres|liter|litre + ltrs|ltr|lt placed before l|L so the
    # longest litre spelling wins (IGNORECASE) — full word avoids matching the bare
    # "lit" prefix of lithium/little/litchi.
    # value also accepts a leading-dot decimal (".3 mL", ".75 L" — pharma dosing);
    # the left lookbehind still rejects a dot glued to a letter/digit ("No.3 ml").
    PackPattern(
        id="value_unit_volume_mass",
        regex=re.compile(
            r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?|[.,]\d+)\s*(?P<unit>ml|mL|ML|liters|litres|liter|litre|ltrs|ltr|lt|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB|Oz)\b",
            re.IGNORECASE,
        ),
        groups=("value", "unit"),
        suppress_window=20,
        lang="any",
        role="canonicalization",
        kind="canon",
    ),
)
