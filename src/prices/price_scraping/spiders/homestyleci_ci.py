"""Homestyle CI (Channel Islands) -- https://homestyleci.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class HomestyleciCiSpider(WooBaseSpider):
    name = "homestyleci_ci"
    allowed_domains = ["homestyleci.com"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://homestyleci.com/wp-json/wc/store/v1/products"

