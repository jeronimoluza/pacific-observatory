"""PasarHub Malaysia fresh-market groceries via WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class PasarhubMySpider(WooBaseSpider):
    name = "pasarhub_my"
    allowed_domains = ["pasarhub.my"]
    BASE_URL = "https://pasarhub.my/wp-json/wc/store/products"
    currency = "MYR"
    language = "en"
