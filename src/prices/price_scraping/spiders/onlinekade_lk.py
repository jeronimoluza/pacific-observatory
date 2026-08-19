"""OnlineKade (Sri Lanka) — https://onlinekade.lk/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class OnlinekadeLkSpider(WooBaseSpider):
    name = "onlinekade_lk"
    allowed_domains = ["onlinekade.lk"]
    currency = "LKR"
    language = "en"
    BASE_URL = "https://onlinekade.lk/wp-json/wc/store/v1/products"
