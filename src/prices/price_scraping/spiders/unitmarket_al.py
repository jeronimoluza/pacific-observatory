"""Unit Market (Albania) — https://unitmarket.al. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class UnitmarketAlSpider(WooBaseSpider):
    name = "unitmarket_al"
    allowed_domains = ["unitmarket.al"]
    currency = "ALL"
    language = "sq"
    BASE_URL = "https://unitmarket.al/wp-json/wc/store/v1/products"
