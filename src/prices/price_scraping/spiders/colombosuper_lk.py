"""ColomboSuper (Sri Lanka) — https://colombosuper.lk/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class ColombosuperLkSpider(WooBaseSpider):
    name = "colombosuper_lk"
    allowed_domains = ["colombosuper.lk"]
    currency = "LKR"
    language = "en"
    BASE_URL = "https://colombosuper.lk/wp-json/wc/store/v1/products"
