"""
Grenada Brewery -- the brewery/beverage-distributor storefront on the
CaribeEats delivery platform
(backend.caribeeats.com/api/business/grenada-brewery).

Flagged as a ready-made next candidate by the 2026-09-01 Grenada pass and
scaffolded here. 32 SKUs across 4 categories: Alcoholic (16 -> COICOP 02.1),
Non-alcoholic (12) and Water (4) (-> COICOP 01.2). Spans two divisions, so
coicop_codes stays unset.

Payload `currency` is XCD, matching countries.yaml grenada.
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class GrenadaBreweryGndSpider(CaribeEatsBaseSpider):
    name = "grenada_brewery_gnd"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "grenada-brewery"
