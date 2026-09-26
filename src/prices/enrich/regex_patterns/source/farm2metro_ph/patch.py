"""farm2metro_ph: "order price / <N> grams" / "order price / <N> kilo(s)" / bare "kilo".

The site quotes size in the LABEL text, not a size field: "Fresh Local Organic
American Kale - order price / 500 grams" / ".../ kilo" / "Denorado Mindoro
Rice - order price / 10 kilos". The shared measure vocab (units.yaml) only has
abbreviated mass surfaces (g, gm, gr, grs, kg); it has no spelled-out
"gram(s)"/"kilo(gram)(s)" surface, so every one of these names fell through to
`item` with no size at all. Scoped here (not a units.yaml edit) because
"grams"/"kilo" bare words would be far riskier picked up shared across every
language/country; a units.yaml addition is proposed separately in the report.

Only the single-value forms are read. Range forms ("13 kls." is not a range,
kept; a genuine range like the pacific_bay_ph "(300-350 grams)" shape does not
appear here) and non-mass shapes ("box 48 pcs", "pack of 10", "per basket")
are left alone -- they need a count reading, not a measure one, and are out of
scope for this patch.

19 names carry a parenthetical PIECE-COUNT RANGE beside the weight ("Fresh
Squid ... [3-4pcs] - order price / 500 grams", "Fresh Live Mud Crab
[Alimango] [4-5pcs] - order price / kilo"): the shared grammar had read the
range's second number as a product count (count=4, no size). These are sold
by weight with the range only describing typical yield per kilo/pack, so
count -> mass (count lost, not a multiplier) is the correct reading, declared
with count_loss=True below.

Measured 2026-09-26 on products_input (all countries; farm2metro_ph is
philippines-only): 1,517 unique names, 1,329 product rows change (rulecheck):
726 item -> mass (grams), 60 item -> mass (kilos), 543 item/count -> mass
(bare kilo, includes 19 count_loss rows below).
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_ORDER_PRICE_GRAMS = PackPattern(
    id="FARM2METRO_ORDER_PRICE_GRAMS",
    regex=re.compile(r"(?i)order\s*price\s*/\s*(?P<value>\d+(?:\.\d+)?)\s*grams?\b"),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.001),
)

_ORDER_PRICE_KILOS = PackPattern(
    id="FARM2METRO_ORDER_PRICE_KILOS",
    regex=re.compile(r"(?i)order\s*price\s*/\s*(?P<value>\d+(?:\.\d+)?)\s*(?:kilo(?:gram)?s?|kls?)\b"),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=1.0),
)

_ORDER_PRICE_BARE_KILO = PackPattern(
    id="FARM2METRO_ORDER_PRICE_BARE_KILO",
    regex=re.compile(r"(?i)order\s*price\s*/\s*kilo\b"),
    groups=(),
    pricing_basis_emit="mass",
    lang="any",
    role="extract",
    kind="pricing_basis_marker",
    bucket="per_unit_marker",
)

PATCH = SourcePatch(
    additions=(_ORDER_PRICE_GRAMS, _ORDER_PRICE_KILOS, _ORDER_PRICE_BARE_KILO),
    intent={
        "FARM2METRO_ORDER_PRICE_GRAMS": Intent(
            why="'order price / <N> grams' states the size in grams",
            expect="item -> mass, count -> mass",
            rows=726,
            examples=(
                "*Fresh Local Organic American Kale - order price / 500 grams",
                "All Natural Local Chili Flakes - order price / 50 grams",
                "Benguet Blend Well Grinded- order price / 250 grams",
                "Danggit (salted dried rabbit fish) from Cebu - order price/100 grams)",
                "Authentic \"Vigan\" Longganisa [Garlic Sausage] - order price / 500 grams",
            ),
            count_loss=True,
        ),
        "FARM2METRO_ORDER_PRICE_KILOS": Intent(
            why="'order price / <N> kilo(s)' states the size in kilos",
            expect="item -> mass",
            rows=60,
            examples=(
                "Balatinao | Balantinaw Rice - order price / 5 kilos",
                "Denorado Mindoro Rice - order price / 10 kilos",
                "Denorado Mindoro Rice - order price / 15 kilos",
                "Denorado Mindoro Rice - order price / 25 kilos sack",
                "Dole Cavendish Banana - order price / 13 kls.",
            ),
        ),
        "FARM2METRO_ORDER_PRICE_BARE_KILO": Intent(
            why="bare 'order price / kilo' is a per-kilo price, amount 1 kg",
            expect="item -> mass, count -> mass",
            rows=543,
            examples=(
                "*Fresh Local Organic American Kale - order price / kilo",
                "Choice-cut Local T-Bone | Tbone Steak - order price / kilo",
                "Crimson Sweet Seedless Red Grapes - order price / kilo",
                "Black Rice From The Cordilleras - order price / kilo",
                "Champorado Rice (Sticky rice) order price / kilo",
            ),
            count_loss=True,
        ),
    },
)
