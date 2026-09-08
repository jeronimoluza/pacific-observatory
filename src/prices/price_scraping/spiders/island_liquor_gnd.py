"""
Island Liquor Grenada -- a liquor/tobacco storefront on the CaribeEats
delivery platform (backend.caribeeats.com/api/business/island-liquor-gnd).

53 SKUs across 8 categories: Alcohol: Liquor (36), Rums (5), Liqueur (2),
Cigarettes (6), Cigars (1) -> COICOP 02.1/02.2, plus a 2-item non-alcoholic
tail (Drinks, Tonic Water) -> 01.2. Two different 3-digit classes, so
coicop_codes stays unset and the classifier assigns per-leaf (same call as
`island_liquor_dm`).

Payload `currency` is XCD, matching countries.yaml grenada. Discovered
2026-09-05 in the CaribeEats grenada region listing (region_id=1473); the
2026-09-01 Grenada pass enumerated only the `service_id=groceries` slice and
missed this vendor, which the platform tags business_type_id=1.
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class IslandLiquorGndSpider(CaribeEatsBaseSpider):
    name = "island_liquor_gnd"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "island-liquor-gnd"
