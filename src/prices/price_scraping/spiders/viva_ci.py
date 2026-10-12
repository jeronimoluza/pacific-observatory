"""Viva meals Jersey (Channel Islands) -- https://viva.je/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class VivaCiSpider(WooBaseSpider):
    name = "viva_ci"
    allowed_domains = ["viva.je"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://viva.je/wp-json/wc/store/v1/products"

