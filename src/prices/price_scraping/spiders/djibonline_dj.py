"""Djibonline (Djibouti) — https://djibonline.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class DjibonlineDjSpider(WooBaseSpider):
    name = "djibonline_dj"
    allowed_domains = ["djibonline.com"]
    currency = "DJF"
    language = "fr"
    BASE_URL = "https://djibonline.com/wp-json/wc/store/v1/products"
