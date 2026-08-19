"""Bravo Supermarket (West Bank & Gaza) — https://bravosupermarket.ps/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class BravosupermarketPsSpider(WooBaseSpider):
    name = "bravosupermarket_ps"
    allowed_domains = ["bravosupermarket.ps", "www.bravosupermarket.ps"]
    currency = "USD"
    language = "en"
    BASE_URL = "https://bravosupermarket.ps/wp-json/wc/store/v1/products"
