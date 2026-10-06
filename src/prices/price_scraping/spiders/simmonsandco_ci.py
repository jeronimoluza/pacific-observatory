"""simmonsandco.com (Channel Islands) -- https://simmonsandco.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class SimmonsandcoCiSpider(WooBaseSpider):
    name = "simmonsandco_ci"
    allowed_domains = ["simmonsandco.com"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://simmonsandco.com/wp-json/wc/store/v1/products"
