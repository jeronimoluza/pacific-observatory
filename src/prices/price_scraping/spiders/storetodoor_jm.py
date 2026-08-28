"""Store To Door Jamaica — https://storetodoorja.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class StoretodoorJmSpider(WooBaseSpider):
    name = "storetodoor_jm"
    allowed_domains = ["storetodoorja.com"]
    currency = "JMD"
    language = "en"
    BASE_URL = "https://storetodoorja.com/wp-json/wc/store/v1/products"
