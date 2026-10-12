"""Fantini Pelletteria -- https://www.fantinipelletteria.it/ (leather goods; shop in San Marino
historic centre, e-commerce authorisation N. 925 SM).

WooCommerce Store API v1, ~1327 products, EUR (probed 2026-10-12). chrome124/chrome120 are
refused by this host; safari17_0 clears it, so the profile is pinned.
Page family: API (/wp-json/wc/store/v1/products).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class FantinipelletteriaSmSpider(WooBaseSpider):
    name = "fantinipelletteria_sm"
    allowed_domains = ["fantinipelletteria.it"]
    currency = "EUR"
    language = "it"
    BASE_URL = "https://www.fantinipelletteria.it/wp-json/wc/store/v1/products"
    IMPERSONATE_PROFILE = "safari17_0"
