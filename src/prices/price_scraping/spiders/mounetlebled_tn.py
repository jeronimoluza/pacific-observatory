"""Mounet Lebled (Tunisia) — https://mounetlebled.com. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class MounetlebledTnSpider(WooBaseSpider):
    name = "mounetlebled_tn"
    allowed_domains = ["mounetlebled.com"]
    currency = "TND"
    language = "fr"
    BASE_URL = "https://mounetlebled.com/wp-json/wc/store/v1/products"
