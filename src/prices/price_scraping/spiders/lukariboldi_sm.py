"""Luka Riboldi San Marino -- https://www.lukariboldi.com/ (fashion; San Marino).

WooCommerce Store API v1, unauthenticated, ~243 products, EUR (probed 2026-10-12).
Page family: API (/wp-json/wc/store/v1/products).
"""

from price_scraping.spiders._woo_base import WooBaseSpider


class LukariboldiSmSpider(WooBaseSpider):
    name = "lukariboldi_sm"
    allowed_domains = ["lukariboldi.com"]
    currency = "EUR"
    language = "it"
    BASE_URL = "https://www.lukariboldi.com/wp-json/wc/store/v1/products"
