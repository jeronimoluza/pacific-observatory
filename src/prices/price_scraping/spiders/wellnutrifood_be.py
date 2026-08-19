"""Wellnutrifood (Belgium) — https://wellnutrifood.be/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class WellnutrifoodBeSpider(WooBaseSpider):
    name = "wellnutrifood_be"
    allowed_domains = ["wellnutrifood.be"]
    currency = "EUR"
    language = "fr"
    BASE_URL = "https://wellnutrifood.be/wp-json/wc/store/v1/products"
