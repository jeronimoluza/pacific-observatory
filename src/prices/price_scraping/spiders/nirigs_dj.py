"""NIRIGS (Djibouti) — https://nirigs.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class NirigsDjSpider(WooBaseSpider):
    name = "nirigs_dj"
    allowed_domains = ["nirigs.com"]
    currency = "DJF"
    language = "fr"
    BASE_URL = "https://nirigs.com/wp-json/wc/store/v1/products"
