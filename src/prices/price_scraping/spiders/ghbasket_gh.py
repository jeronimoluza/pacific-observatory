"""GHBasket (Ghana) — https://ghbasket.com/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class GhbasketGhSpider(WooBaseSpider):
    name = "ghbasket_gh"
    allowed_domains = ["ghbasket.com"]
    currency = "GHS"
    language = "en"
    BASE_URL = "https://ghbasket.com/wp-json/wc/store/v1/products"
