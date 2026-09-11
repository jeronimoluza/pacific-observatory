"""Original Fish (Switzerland) — https://original-fish.ch. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class OriginalfishChSpider(WooBaseSpider):
    name = "originalfish_ch"
    allowed_domains = ["original-fish.ch"]
    currency = "CHF"
    language = "de"
    BASE_URL = "https://original-fish.ch/wp-json/wc/store/v1/products"
