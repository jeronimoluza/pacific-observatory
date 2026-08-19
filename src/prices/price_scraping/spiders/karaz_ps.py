"""Karaz Supermarket (West Bank & Gaza) — https://karaz.ps/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class KarazPsSpider(WooBaseSpider):
    name = "karaz_ps"
    allowed_domains = ["karaz.ps", "www.karaz.ps"]
    currency = "ILS"
    language = "en"
    BASE_URL = "https://karaz.ps/wp-json/wc/store/v1/products"
