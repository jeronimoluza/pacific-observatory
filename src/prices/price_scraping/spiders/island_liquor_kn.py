"""
Island Liquor St Kitts -- a liquor/tobacco storefront on the CaribeEats
delivery platform (backend.caribeeats.com/api/business/island-liquor).

Narrow COICOP-02 source: 117 SKUs across 4 categories (Liquor 93,
Cigarettes 14, Vape 9, JUUL 1). Identified but not shipped by the
2026-09-01 pass, which prioritised the larger RAMS St Kitts catalogue.

Do NOT confuse with `island_liquor_dm` (slug `island-liquor-dominica`) or
`island_liquor_gnd` (slug `island-liquor-gnd`) -- same brand family, three
different territories, three different CaribeEats slugs and price levels.

Currency: payload reports USD. Verified 2026-09-05 against the Dominica
sibling (XCD payload) on 19 verbatim-shared product names -- median price
ratio 0.37 = 1/2.70, exactly the XCD/USD peg, so the USD label is real and
not a platform misconfiguration.
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class IslandLiquorKnSpider(CaribeEatsBaseSpider):
    name = "island_liquor_kn"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "island-liquor"
