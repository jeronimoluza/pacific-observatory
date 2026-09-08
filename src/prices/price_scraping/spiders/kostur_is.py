"""Kostur (Iceland) — https://kostur.is/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class KosturIsSpider(WooBaseSpider):
    name = "kostur_is"
    allowed_domains = ["kostur.is"]
    currency = "ISK"
    language = "is"
    BASE_URL = "https://kostur.is/wp-json/wc/store/v1/products"
