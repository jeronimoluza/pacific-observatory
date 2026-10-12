"""Reuseit Jersey (Channel Islands) -- https://reuseit.je/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class ReuseitCiSpider(WooBaseSpider):
    name = "reuseit_ci"
    allowed_domains = ["reuseit.je"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://reuseit.je/wp-json/wc/store/v1/products"

