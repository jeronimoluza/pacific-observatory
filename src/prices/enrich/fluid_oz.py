"""Leaf-aware fluid-ounce correction for beverage rows.

An "oz" on a drink is a FLUID ounce (volume); the unit table only knows the
weight one, because `extract.py` runs before any leaf is known and has no
textual way to tell the two apart. On 02.1 (alcoholic beverages) it always is
the fluid one, so a 12 fl oz beer was filed as 340 g and priced per kilogram in
a division priced per litre everywhere else.

Lives outside `stages/classify.py` (the only caller) purely for that file's line
budget, and is applied there BEFORE the basis-audit — which would otherwise rule
on a basis this correction is about to replace.
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.unit_tables import UNIT_MAP

_ALCOHOL_PREFIX = "02.1"
_FL_OZ_LT = 0.0295735  # US fluid ounce, in litres
_OZ_MEASURE_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?P<value>\d+(?:[.,]\d+)?)\s*(?:fl\.?\s*)?oz\b", re.IGNORECASE
)


def remap_fluid_oz(row: dict, name: str) -> None:
    """Re-read an alcoholic drink's ounce measure as volume, in place.

    Only fires when the name's ounce figure IS the mass the extractor emitted,
    so a name mentioning ounces alongside some other measure is left alone."""
    if not str(row.get("coicop_code") or "").startswith(_ALCOHOL_PREFIX):
        return
    if row.get("pricing_basis") != "mass" or row.get("standard_unit") != "kg":
        return
    amount = row.get("amount_value")
    if amount is None:
        return
    for m in _OZ_MEASURE_RE.finditer(name):
        ounces = float(m.group("value").replace(",", "."))
        if abs(ounces * UNIT_MAP["oz"].mul - float(amount)) < 1e-9:
            row["pricing_basis"] = "volume"
            row["standard_unit"] = "lt"
            row["amount_value"] = ounces * _FL_OZ_LT
            return
