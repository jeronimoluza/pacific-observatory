"""tech.je (Channel Islands) -- https://tech.je/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class TechjeCiSpider(WooBaseSpider):
    name = "techje_ci"
    allowed_domains = ["tech.je"]
    currency = "GBP"
    language = "en"
    BASE_URL = "https://tech.je/wp-json/wc/store/v1/products"
