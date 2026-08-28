"""Miabe Marche (Togo) — https://miabemarche.tg/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class MiabemarcheTgSpider(WooBaseSpider):
    name = "miabemarche_tg"
    allowed_domains = ["miabemarche.tg"]
    currency = "XOF"
    language = "fr"
    BASE_URL = "https://miabemarche.tg/wp-json/wc/store/v1/products"
