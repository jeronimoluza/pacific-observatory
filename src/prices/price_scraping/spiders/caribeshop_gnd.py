"""
CaribeShop Grenada -- a general-goods storefront on the CaribeEats delivery
platform (backend.caribeeats.com/api/business/caribeshop--gnd).

Confirmed food-led: 39 categories, 1180 SKUs, majority food/beverage
(Breakfast-Cereals, Canned/Jarred Goods, Beverages, Teas, Snacks, Pasta,
Rice, Sauce & Salsa, Jams/Jellies, Coffee, Seasonings, Fish, Bottled Water,
...) alongside a Personal Care / Baby Care / Cleaners / OTC-meds minority.
Real branded SKUs with per-unit prices (e.g. "Sensodyne Rapid Relief Tooth
Paste" 34.67, "Brunswick Sardines In Spring Water 106g" 5.07) -- not the
"personalized shopping" placeholder-price model that the platform's
Real Value Supermarket Grenada listing uses (that one has an empty
categories list and a shopper-service disclaimer -- skipped, see
known_blockers.md).

Currency read from the payload (XCD, matches countries.yaml grenada).
"""

from price_scraping.spiders._caribeeats_base import CaribeEatsBaseSpider


class CaribeshopGndSpider(CaribeEatsBaseSpider):
    name = "caribeshop_gnd"
    allowed_domains = ["backend.caribeeats.com"]
    language = "en"
    SLUG = "caribeshop--gnd"
