"""Global unit-lookup tables consumed alongside the regex tree.

Translated verbatim from `static/pack_patterns.yaml::unit_norm` and
`static/regex_units.yaml::unit_map`. These are language-agnostic, not
country-overridable, so they live outside the per-country composition tree.

- UNIT_NORM: case-fold + variant-spelling + CJK suffix → canonical unit string.
- UNIT_MAP:  canonical unit → UnitEmit(basis, su, mul).
"""

from __future__ import annotations

from typing import Mapping

from prices.enrich.regex_patterns.types import UnitEmit


UNIT_NORM: Mapping[str, str] = {
    "ml": "ml",
    "mL": "ml",
    "ML": "ml",
    "l": "l",
    "L": "l",
    "lt": "l",
    "ltr": "l",
    "ltrs": "l",
    "liter": "l",
    "litre": "l",
    "liters": "l",
    "litres": "l",
    "g": "g",
    "G": "g",
    "kg": "kg",
    "KG": "kg",
    "mg": "mg",
    "MG": "mg",
    "gm": "g",
    "GM": "g",
    "gr": "g",
    "GR": "g",
    "oz": "oz",
    "OZ": "oz",
    "Oz": "oz",
    "lb": "lb",
    "LB": "lb",
    "公升": "l",
    "毫升": "ml",
    "公斤": "kg",
    "公克": "g",
    "克": "g",
    "升": "l",
}


UNIT_MAP: Mapping[str, UnitEmit] = {
    "g": UnitEmit(basis="mass", su="kg", mul=0.001),
    "kg": UnitEmit(basis="mass", su="kg", mul=1.0),
    "mg": UnitEmit(basis="mass", su="kg", mul=0.000001),
    "oz": UnitEmit(basis="mass", su="kg", mul=0.0283495),
    "lb": UnitEmit(basis="mass", su="kg", mul=0.453592),
    "ml": UnitEmit(basis="volume", su="lt", mul=0.001),
    "l": UnitEmit(basis="volume", su="lt", mul=1.0),
    "cl": UnitEmit(basis="volume", su="lt", mul=0.01),
}
