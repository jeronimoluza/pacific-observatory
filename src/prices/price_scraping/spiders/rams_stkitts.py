"""
RAMS St Kitts -- a named supermarket storefront on the CaribeEats delivery
platform (backend.caribeeats.com/api/business/rams-st-kitts).

RAMS is a known Caribbean grocery/liquor chain. This listing carries 1013
real branded SKUs across 40 categories (produce, dairy substitutes/frozen
meals, snacks, pantry staples, wine/spirits) -- e.g. "KIT KAT 4 FINGERS -
2 PK" 6.50, "GRAPES GREEN SEEDLESS - 2 LB" 18.50, "LUIES FELIPE EDWARDS
SAUVIGNON BLANC - 750 ML" 22.25.

Currency read from the payload (XCD, matches countries.yaml
st_kitts_and_nevis).
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class RamsStkittsSpider(CaribeEatsBaseSpider):
    name = "rams_stkitts"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "rams-st-kitts"
