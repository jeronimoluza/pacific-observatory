"""Boucherie Buffat (Switzerland) — https://boucherie-buffat.ch. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class BoucheriebuffatChSpider(WooBaseSpider):
    name = "boucheriebuffat_ch"
    allowed_domains = ["boucherie-buffat.ch"]
    currency = "CHF"
    language = "fr"
    BASE_URL = "https://boucherie-buffat.ch/wp-json/wc/store/v1/products"
