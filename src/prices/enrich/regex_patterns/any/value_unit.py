"""Single value+unit pattern (the common case) — canonicalization role."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

# FIXME (BUG 3): Appliance "99L" / "120L" false volume extraction.
# PackPattern.suppress_window is scaffolded but has no consumer in extract.py.
# When suppress_window is wired, add a suppress pattern that blocks
# value_unit_volume_mass from emitting when these appliance keywords appear
# within N chars of the match:
#   freezer, fridge, refrigerator, washer, dryer, oven, microwave,
#   vacuum, dishwasher, tank, bin, cooler
# Concrete failing case: "99L Chest Freezer" → basis=volume (wrong), should be item.
# Do NOT implement until the suppress_window consumer is added to extract.py.

# FIXME (BUG 4): Apparel fabric-weight "5.6oz" false mass extraction.
# Same suppress_window mechanism as BUG 3. Appliance-style suppress_window
# needed for these apparel keywords near an oz/g match:
#   t-shirt, tee, shirt, jeans, shorts, dress, hoodie, sweatshirt,
#   trackpants, socks, underwear, bra
# Concrete failing case: "T-shirt 5.6oz Heavyweight" → basis=mass (wrong), should be item.
# Do NOT implement until the suppress_window consumer is added to extract.py.

PATTERNS: tuple[PackPattern, ...] = (
    # "500g", "1L", "135ml", "158GM", "60gr", "25mg"
    PackPattern(
        id="value_unit_volume_mass",
        regex=re.compile(
            r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB|Oz)\b",
            re.IGNORECASE,
        ),
        groups=("value", "unit"),
        lang="any",
        role="canonicalization",
    ),
)
