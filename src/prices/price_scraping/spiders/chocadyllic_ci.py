"""chocadyllic.co.uk (Channel Islands) -- https://chocadyllic.co.uk/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class ChocadyllicCiSpider(WooBaseSpider):
    name = "chocadyllic_ci"
    allowed_domains = ["chocadyllic.co.uk"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://chocadyllic.co.uk/wp-json/wc/store/v1/products"
