"""PametnoKupuj (Bosnia and Herzegovina) — https://pametnokupuj.ba/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class PametnokupujBaSpider(WooBaseSpider):
    name = "pametnokupuj_ba"
    allowed_domains = ["pametnokupuj.ba"]
    currency = "BAM"
    language = "bs"
    BASE_URL = "https://pametnokupuj.ba/wp-json/wc/store/v1/products"
