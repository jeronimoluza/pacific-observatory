"""
IslandSelects (Turks and Caicos) -- https://islandselectstci.com/

Grocery delivery storefront for Turks and Caicos on WooCommerce. Probed
2026-09-11: plain `requests` (no TLS impersonation) gets a clean 200 from
the WooCommerce Store API (/wp-json/wc/store/v1/products), server header
LiteSpeed, no WAF challenge on any of the three probe arms.

X-WP-Total: 1400 products. Enumerability confirmed: page1 vs page2 ids
disjoint. USD, currency_minor_unit=2. Real grocery SKUs across Canned
Fruits & Vegetables, Meats & Seafood, Snacks (IGA-branded and national
brands: Motts, Oscar Mayer, Act 2, Orville). Distinct catalog/backend from
tcgrocerydelivery_tc and from the existing goods2door_tc (Wix) source --
different platform, different product ids, not a duplicate shelf.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class IslandSelectsTcSpider(WooBaseSpider):
    name = "islandselects_tc"
    allowed_domains = ["islandselectstci.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://islandselectstci.com/wp-json/wc/store/v1/products"
