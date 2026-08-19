"""Venavo (Netherlands) — https://www.venavo.nl/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class VenavoNlSpider(WooBaseSpider):
    name = "venavo_nl"
    allowed_domains = ["venavo.nl"]
    currency = "EUR"
    language = "nl"
    BASE_URL = "https://www.venavo.nl/wp-json/wc/store/v1/products"
