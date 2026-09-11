"""The Butcher Shop (Tanzania) — https://butchershop.co.tz. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class ButchershopTzSpider(WooBaseSpider):
    name = "butchershop_tz"
    allowed_domains = ["butchershop.co.tz"]
    currency = "TZS"
    language = "en"
    BASE_URL = "https://butchershop.co.tz/wp-json/wc/store/v1/products"
