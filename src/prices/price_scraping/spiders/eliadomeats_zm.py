"""Eliado Meats (Zambia) — https://eliadomeats.com. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class EliadomeatsZmSpider(WooBaseSpider):
    name = "eliadomeats_zm"
    allowed_domains = ["eliadomeats.com"]
    currency = "ZMW"
    language = "en"
    BASE_URL = "https://eliadomeats.com/wp-json/wc/store/v1/products"
