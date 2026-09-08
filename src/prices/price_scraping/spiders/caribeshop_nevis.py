"""
CaribeShop Nevis -- a general-goods, food-led storefront on the CaribeEats
delivery platform (backend.caribeeats.com/api/business/caribeshop-nevis).

Handed forward as a ready-made candidate by the 2026-09-01 St. Kitts and
Nevis pass and scaffolded here. 1,166 SKUs across 57 categories, majority
food/beverage (Breakfast-Cereals, cooking oil, Beverages, Snacks, Prepared
Foods, Fresh Fruits & Vegetables, Dairy, Coffee, Frozen) against a
Pet/Personal-Care/Cleaners minority.

Currency: the payload reports USD, which the previous pass flagged as
possibly wrong for Nevis (XCD is legal tender). Re-verified 2026-09-05 and
the field is CORRECT: 13 product names are shared verbatim with
`rams_stkitts` (whose payload currency is XCD) and the median price ratio
across them is 0.354 -- i.e. 1/2.82, essentially the 1:2.70 XCD/USD peg.
This business genuinely prices in USD; the base spider reads currency from
the payload rather than hardcoding it.
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class CaribeshopNevisSpider(CaribeEatsBaseSpider):
    name = "caribeshop_nevis"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "caribeshop-nevis"
