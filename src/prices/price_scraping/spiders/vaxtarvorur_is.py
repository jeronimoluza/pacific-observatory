"""Vaxtarvörur (Iceland) — https://vaxtarvorur.is/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class VaxtarvorurIsSpider(WooBaseSpider):
    name = "vaxtarvorur_is"
    allowed_domains = ["vaxtarvorur.is"]
    currency = "ISK"
    language = "is"
    BASE_URL = "https://vaxtarvorur.is/wp-json/wc/store/v1/products"
