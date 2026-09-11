"""
TC Grocery Delivery (Turks and Caicos) -- https://turksandcaicosgrocerydelivery.com/

"TCI Online Food Store" -- WooCommerce grocery/liquor delivery storefront for
Providenciales and the wider Turks and Caicos Islands. Probed 2026-09-11:
plain `requests` (no TLS impersonation) gets a clean 200 from the WooCommerce
Store API (/wp-json/wc/store/v1/products); `curl_cffi impersonate=chrome124`
gets a 403 from `server: hcdn` -- a JA3 denylist aimed at impersonated
clients, not a real block (matches the documented hcdn pattern). Scrapy's
CompositeDownloadHandler already defaults to plain Twisted HTTP unless
meta['impersonate'] is set, so no special handling needed here -- just don't
set IMPERSONATE_PROFILE.

X-WP-Total: 946 products. Enumerability confirmed: page1 vs page2 ids
disjoint. USD, currency_minor_unit=2. Real grocery SKUs across BEVERAGES,
Fruit Cup, Candy Bars, Granola Bars, Fruit Snacks, etc.

A sibling domain, turksandcaicosgrocerydeliveryservice.com, serves the
IDENTICAL catalog (same product ids, e.g. id 3322 "Oikos Greek Yogurt 0%" on
both) -- same backend, two marketing domains. Deliberately NOT onboarded as a
second source to avoid double-counting this shelf.
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class TcGroceryDeliveryTcSpider(WooBaseSpider):
    name = "tcgrocerydelivery_tc"
    allowed_domains = ["turksandcaicosgrocerydelivery.com"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://turksandcaicosgrocerydelivery.com/wp-json/wc/store/v1/products"
