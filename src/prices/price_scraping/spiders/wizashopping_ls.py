"""Wiza Shopping (Lesotho) — https://wizashopping.co.ls/. Multi-retailer price-comparison WooCommerce hub."""

from price_scraping.spiders._woo_base import WooBaseSpider


class WizashoppingLsSpider(WooBaseSpider):
    name = "wizashopping_ls"
    allowed_domains = ["wizashopping.co.ls"]
    currency = "LSL"
    language = "en"
    BASE_URL = "https://wizashopping.co.ls/wp-json/wc/store/v1/products"
