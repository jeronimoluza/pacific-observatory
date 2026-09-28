"""
Raena Shop — https://raenashop.com/.

Eritrean/Ethiopian diaspora import store (Netherlands-based; EUR pricing,
no ERN storefront). Standard WooCommerce Store API, confirmed open and
enumerable (287 products across 15 pages, page 1/page 2 fully disjoint).
Mixed catalog: cosmetics, home/kitchen accessories (coffee-ceremony sets),
food and herbs (coffee, spices, imported flours) — first-party inventory,
non-grocery-led, so channel is dept-store rather than supermarket.

Filed under the Netherlands, not Eritrea: the shop sells and ships inside
Europe, never delivers in Eritrea, and prices only in EUR, so its prices are a
Dutch price level for imported Horn-of-Africa goods (moved 2026-09-28, W40).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class RaenashopNlSpider(WooBaseSpider):
    name = "raenashop_nl"
    allowed_domains = ["raenashop.com"]
    currency = "EUR"
    language = "en"
    BASE_URL = "https://raenashop.com/wp-json/wc/store/v1/products"
