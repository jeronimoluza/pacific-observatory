"""LOOP Ltd (Guernsey) (Channel Islands) -- https://www.loop.gg/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class LoopCiSpider(WooBaseSpider):
    name = "loop_ci"
    allowed_domains = ["www.loop.gg"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://www.loop.gg/wp-json/wc/store/v1/products"

