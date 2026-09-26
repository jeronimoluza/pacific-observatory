"""coopmart: a trailing "kg-<supplier code>" means the price is per kilogram.

Loose produce, meat and fish carry the weighing unit and a supplier code glued
by a hyphen ("Thịt đùi bò kg-TD", "Lườn cá hồi kg-PGP990"). The shared BARE_KG
marker refuses a hyphen after "kg" on purpose, so these names fell through to
`item` and Stage B had to guess their size. This marker reads them as per kg
(amount 1 kg), and only where no measure was found: "450g up kg-MIAF" keeps
its 450 g (wrong too -- a per-kg mango over 450 g -- but a canon replacement,
not a marker, is what would fix it).

Measured 2026-09-26 on products_input (09-20): 106 coopmart names carry the
suffix, 105 move item -> mass (rulecheck).
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_KG_SUPPLIER = PackPattern(
    id="COOPMART_KG_SUPPLIER",
    regex=re.compile(r"(?i)\bkg-[a-z]"),
    groups=(),
    pricing_basis_emit="mass",
    lang="any",
    role="extract",
    kind="pricing_basis_marker",
    bucket="per_unit_marker",
)

PATCH = SourcePatch(
    additions=(_KG_SUPPLIER,),
    intent={
        "COOPMART_KG_SUPPLIER": Intent(
            why="'<name> kg-<supplier code>' is a per-kg price on loose goods",
            expect="item -> mass",
            rows=105,
            examples=(
                "Thịt đùi bò kg-TD",
                "Lườn cá hồi kg-PGP990",
                "Cá lóc đen nguyên con làm sạch kg-NCC-TD",
                "Tôm thẻ kg-PGP 990",
                "Dưa lưới đế mật ruột cam Co.op Select kg-PL",
            ),
        ),
    },
)
