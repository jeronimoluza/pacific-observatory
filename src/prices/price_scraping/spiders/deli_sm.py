"""Delì San Marino -- https://www.deli.sm/ (perfumery, leather goods, footwear, watches; San Marino).

WooCommerce Store API v1, unauthenticated, ~997 products, EUR (probed 2026-10-12).
Page family: API (/wp-json/wc/store/v1/products).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class DeliSmSpider(WooBaseSpider):
    name = "deli_sm"
    allowed_domains = ["deli.sm"]
    currency = "EUR"
    language = "it"
    BASE_URL = "https://www.deli.sm/wp-json/wc/store/v1/products"
