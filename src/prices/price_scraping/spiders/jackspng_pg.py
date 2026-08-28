"""Jacks (Papua New Guinea) -- https://jackspng.com/. Clothing/apparel department
store chain. Round 3 platform-fingerprint reversal (prior round never dispatched
this domain). WooCommerce Store API is open."""

from price_scraping.spiders._woo_base import WooBaseSpider


class JackspngPgSpider(WooBaseSpider):
    name = "jackspng_pg"
    allowed_domains = ["jackspng.com"]
    currency = "PGK"
    language = "en"
    BASE_URL = "https://jackspng.com/wp-json/wc/store/v1/products"
