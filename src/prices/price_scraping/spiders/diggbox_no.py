"""DiggBox (Norway) — https://www.diggbox.no/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class DiggboxNoSpider(WooBaseSpider):
    name = "diggbox_no"
    allowed_domains = ["diggbox.no"]
    currency = "NOK"
    language = "no"
    BASE_URL = "https://www.diggbox.no/wp-json/wc/store/v1/products"
