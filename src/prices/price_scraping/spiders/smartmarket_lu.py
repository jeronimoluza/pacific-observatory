"""Smartmarket (Luxembourg) — https://smartmarket.lu/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class SmartmarketLuSpider(WooBaseSpider):
    name = "smartmarket_lu"
    allowed_domains = ["smartmarket.lu"]
    currency = "EUR"
    language = "fr"
    BASE_URL = "https://smartmarket.lu/wp-json/wc/store/v1/products"
