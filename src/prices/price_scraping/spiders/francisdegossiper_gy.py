"""
Spider for Francis De Gossiper (Guyana) - https://francisdegossiper.com/

WooCommerce multi-vendor marketplace (Dokan/WCFM-style) with 425 products
across many vendor stores. Most of the catalogue is restaurant-style prepared
food (rotisserie, chow mein, appetizers -- COICOP 11, out of scope for a
food-RETAIL source), so this spider deliberately narrows to the
`wp-json/wc/store/v1/products` category IDs that are genuine COICOP 01/02
raw grocery/meat/produce/beverage categories (confirmed by sampling each
category's contents before selecting it) -- 158 products total. `channel` is
`marketplace` (not `supermarket`) since these are third-party vendor
listings, not one retailer's own catalogue.

Prices are returned in MINOR UNITS (cents) -- `currency_minor_unit: 2`
confirmed on every sampled product; divide by 100.

NOTE: "beef-and-mutton", "chicken", "pork", "seafood", and "vegetable" are
NOT included below despite grocery-sounding names -- sampling confirmed every
one of those five categories is entirely Chinese-restaurant prepared dishes
("Stir Fried Mutton With Cumin", "Kung Pao Chicken", "Crispy ToFu"), i.e.
COICOP 11 restaurant meals, not retail groceries. Only the `grocery-*`
prefixed categories and `beverages-drinks` were confirmed as genuine
raw/packaged retail items (Carnation evaporated milk, 2L Coca-Cola, etc.).
"""

import html
import logging

import scrapy

logger = logging.getLogger(__name__)

# category id -> slug, restricted to categories SAMPLED and CONFIRMED to be
# genuine COICOP 01/02 packaged-grocery/beverage retail items.
CATEGORIES = {
    80: "beverages-drinks",
    15: "grocery",
    63: "grocery-cold-cereal",
    90: "grocery-all-kitchen-oil",
    97: "grocery-all-varieties-of-cookies-biscuits",
    91: "grocery-breakfast-cereal",
    87: "grocery-cereal-pasta",
    65: "grocery-dairy-chilled-products",
    68: "grocery-seasoning-spices-stuffing",
}

API_BASE = "https://francisdegossiper.com/wp-json/wc/store/v1/products"
PAGE_SIZE = 50


class FrancisdegossiperGySpider(scrapy.Spider):
    name = "francisdegossiper_gy"
    allowed_domains = ["francisdegossiper.com"]
    currency = "GYD"
    language = "en"

    def start_requests(self):
        for cat_id, slug in CATEGORIES.items():
            yield scrapy.Request(
                f"{API_BASE}?category={cat_id}&per_page={PAGE_SIZE}&page=1",
                callback=self.parse_page,
                meta={"category": slug, "cat_id": cat_id, "page": 1},
            )

    def parse_page(self, response):
        data = response.json()
        category = response.meta["category"]
        if not data:
            return
        for p in data:
            # The Store API returns seller-authored names with raw HTML
            # entities ("Mario&#8217;s pasta"). 119 sibling spiders already
            # unescape; without it the entity text reaches the classifier.
            name = html.unescape((p.get("name") or "")).strip()
            prices = p.get("prices") or {}
            minor_unit = prices.get("currency_minor_unit", 2)
            raw_price = prices.get("price")
            if not name or raw_price is None:
                continue
            price = float(raw_price) / (10**minor_unit)
            if price <= 0:
                continue
            yield {
                "product_id": p.get("id"),
                "product_name": name,
                "price": price,
                "currency": prices.get("currency_code", self.currency),
                "category": category,
                "url": p.get("permalink"),
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if len(data) == PAGE_SIZE:
            next_page = response.meta["page"] + 1
            yield scrapy.Request(
                f"{API_BASE}?category={response.meta['cat_id']}&per_page={PAGE_SIZE}&page={next_page}",
                callback=self.parse_page,
                meta={**response.meta, "page": next_page},
            )
