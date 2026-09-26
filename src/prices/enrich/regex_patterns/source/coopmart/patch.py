"""coopmart: a trailing "kg-<supplier code>" means the price is per kilogram;
a mass unit glued straight to a brand name still ends the measure.

Loose produce, meat and fish carry the weighing unit and a supplier code glued
by a hyphen ("Thịt đùi bò kg-TD", "Lườn cá hồi kg-PGP990"). The shared BARE_KG
marker refuses a hyphen after "kg" on purpose, so these names fell through to
`item` and Stage B had to guess their size. This marker reads them as per kg
(amount 1 kg), and only where no measure was found: "450g up kg-MIAF" keeps
its 450 g (wrong too -- a per-kg mango over 450 g -- but a canon replacement,
not a marker, is what would fix it).

"Lòng trắng trứng gà tiệt trùng 250gV.food" glues the gram unit straight to
the brand "V.food" with no space or punctuation; the shared gram pattern needs
a word boundary after "g" and never fires, so the name fell through to a
default egg count (4) instead of its stated 250 g. This canon pattern ends the
measure at "g" when the next character is an upper-case letter starting a
glued word, unless that word is "up" ("500gUp", "350gUp kg" -- the same
unfixed per-kg-minimum shape as "450g up kg-MIAF" above, left alone).

Measured 2026-09-26 on products_input (09-20): 1 coopmart product carries the
suffix (23 price observations over time in Stage B output), item -> mass
(rulecheck).
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
_GRAM_GLUED_BRAND = PackPattern(
    id="COOPMART_GRAM_GLUED_BRAND",
    regex=re.compile(r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[gG])(?!\s?[Uu]p\b)(?=[A-ZĐ])"),
    groups=("value", "unit"),
    lang="any",
    role="canonicalization",
    kind="canon",
    bucket="single_measure",
)

PATCH = SourcePatch(
    additions=(_KG_SUPPLIER, _GRAM_GLUED_BRAND),
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
        "COOPMART_GRAM_GLUED_BRAND": Intent(
            why="'<N>g<Brand>' with no space still ends the gram measure at 'g'",
            expect="item -> mass",
            rows=1,
            examples=(
                "Lòng trắng trứng gà tiệt trùng 250gV.food",
            ),
        ),
    },
)
