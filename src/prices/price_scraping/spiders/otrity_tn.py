"""Otrity (Tunisia) — https://otrity.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class OtrityTnSpider(WooBaseSpider):
    name = "otrity_tn"
    allowed_domains = ["otrity.com"]
    currency = "TND"
    language = "fr"
    BASE_URL = "https://otrity.com/wp-json/wc/store/v1/products"
