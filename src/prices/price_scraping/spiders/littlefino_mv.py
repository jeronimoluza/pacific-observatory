"""LittleFINO (Maldives) — https://fino.com.mv/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class LittlefinoMvSpider(WooBaseSpider):
    name = "littlefino_mv"
    allowed_domains = ["fino.com.mv"]
    currency = "MVR"
    language = "en"
    BASE_URL = "https://fino.com.mv/wp-json/wc/store/v1/products"
