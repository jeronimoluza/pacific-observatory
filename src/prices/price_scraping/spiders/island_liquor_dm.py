"""
Island Liquor Dominica -- a liquor/tobacco storefront on the CaribeEats
delivery platform (backend.caribeeats.com/api/business/island-liquor-dominica).

Narrow COICOP 02 source (alcohol + tobacco): 42 SKUs across 7 categories
(Liquor, Rums, Wine, Liqueur, Cigarettes, Cigars). The platform's other
Dominica listing, CaribeShop DM (caribeshop-dm), was probed and rejected --
6206 SKUs but only ~8% food/beverage (Foods & Beverages category = 483 of
6206; the catalogue is dominated by Personal Care/OTC/Household), which
fails the food-and-beverage-led criterion -- see known_blockers.md.

Currency read from the payload (XCD, matches countries.yaml dominica).
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class IslandLiquorDmSpider(CaribeEatsBaseSpider):
    name = "island_liquor_dm"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "island-liquor-dominica"
