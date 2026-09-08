"""
Carib Brewery Nevis -- the brewery/beverage-distributor storefront on the
CaribeEats delivery platform
(backend.caribeeats.com/api/business/carib-brewery-nevis).

69 SKUs across 2 categories: Alcoholic (13 -- beers, stouts, malt-based
mixes -> COICOP 02.1) and Non-Alcoholic (56 -- soft drinks, malts, juices,
water -> COICOP 01.2). coicop_codes left unset: the catalogue spans two
different divisions, so the narrowness rule does not apply and the
classifier assigns per-leaf.

Payload `currency` is XCD, matching countries.yaml st_kitts_and_nevis. The
St Kitts sibling storefront (`carib-brewery`, 17 SKUs) is the same brewery's
much smaller listing and was NOT onboarded separately -- it would
double-count one shelf.
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class CaribBreweryNevisSpider(CaribeEatsBaseSpider):
    name = "carib_brewery_nevis"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "carib-brewery-nevis"
