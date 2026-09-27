"""pasar_segar: spelled-out "gram" size word.

Indonesian shoppers write mass with the abbreviations already in
`units.yaml` (g, gr, kg), but pasar_segar's own catalogue frequently spells
the unit out in full: "Asparagus Perpack (250 gram) - Eat Me", "pop mie
pedes dower 75 gram", "Ajinomoto Bumbu Penyedap Micin 250 gram". The shared
measure vocab has no spelled-out "gram" surface (the same gap the Philippines
and New Zealand pilots flagged for English "grams"), so every one of these
names fell through to `item` with no size at all. Scoped here (not a
units.yaml edit) for the same reason as the farm2metro_ph precedent: a bare
"gram" word picked up shared, across every language, would be far riskier
than one source's own regex.

Checked and dropped: a spelled-out "liter"/"litre" pattern was tried first
(pasar_segar has ~6 names like "minyak sunco 1 liter", "le minerale 15
liter") but `units.yaml` already lists `liter`/`litre`/`liters`/`litres` as
volume surfaces (line ~34) -- rulecheck confirmed 0 rows moved and refused
the entry ("no longer moves") because these names were already read
correctly without any patch. Only "gram" is a genuine gap.

Value is captured as plain digits with an optional COMMA decimal only
(`\\d+(?:,\\d+)?`) -- deliberately NOT `[.,]`. Indonesian writes "." as the
thousands separator and "," as the decimal point (opposite of English), and
the shared value parser (`extract.py::_match_extra_unit`) always does
`float(value.replace(",", "."))`, with no thousands-grouping awareness. A
value regex that allowed a bare dot would silently misread a thousands-
grouped size ("1.000 Gram" = 1000 g) as 1.0 g, the exact bug class the
Thailand pilot found in shared `grammar.py._VAL` (comma-as-decimal
misparsing "1,000" bulk sizes) mirrored onto dots. Excluding the dot leaves
that one shape ("Labu Acar Berat 1.000 Gram", 1 pasar_segar name) unmatched
and unchanged (still `item`, no worse than before) rather than parsed 1000x
too small.

11 rows read a piece count glued next to a total pack mass ("Ki Pao isi Keju
25 Pcs 430 Gram", "Cedea Ebi Furia 10 Pcs 230 Gram (GORENG)") as count=25/10
before this patch; the number beside "Gram" is the pack's total weight, not
a per-piece size, so the bogus count is correctly dropped (count_loss, same
reading as the Vietnam/Philippines "count beside a total mass is inert
contents" precedent).

Measured 2026-09-26 with `rulecheck source pasar_segar` (pasar_segar is
indonesia-only): 563 product rows move, all item -> mass, 11 with
count_loss. Verdict: model_review.

"N ons" (2026-09-27) is the Indonesian ons, 100 g ("Lada Hitam 1 Ons",
"Brokoli 5 ons"); 176 01+02.1 names fell to item. Same value shape as "gram",
and not after "/": "1/2 ons" must not read as 2 ons (it stays item).
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_GRAM = PackPattern(
    id="PASAR_SEGAR_GRAM",
    regex=re.compile(r"(?<![\d.,])(?P<value>\d+(?:,\d+)?)\s*gram\b", re.IGNORECASE),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.001),
)

_ONS = PackPattern(
    id="PASAR_SEGAR_ONS",
    regex=re.compile(r"(?<![\d.,/])(?P<value>\d+(?:,\d+)?)\s*ons\b", re.IGNORECASE),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.1),
)

PATCH = SourcePatch(
    additions=(_GRAM, _ONS),
    intent={
        "PASAR_SEGAR_GRAM": Intent(
            why="spelled-out 'gram' states the size in grams",
            expect="item -> mass, count -> mass",
            rows=563,
            examples=(
                "Asparagus Perpack (250 gram) - Eat Me",
                "pop mie pedes dower 75 gram",
                "Bihun  cap tanam jagung 320 gram",
                "Daging Sapi Rendang 250 gram",
                "Ajinomoto Bumbu Penyedap Micin 250 gram",
            ),
            count_loss=True,
        ),
        "PASAR_SEGAR_ONS": Intent(
            why="'N ons' is N x 100 g (Indonesian ons)",
            expect="item -> mass",
            rows=176,
            examples=(
                "Lada Hitam 1 Ons",
                "Brokoli 5 ons",
                "Ikan Teri Nasi Kering 1 Ons",
            ),
        ),
    },
)
