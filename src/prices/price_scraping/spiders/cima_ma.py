"""Cimamarket (Morocco) — https://cima.ma/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class CimaMaSpider(WooBaseSpider):
    name = "cima_ma"
    allowed_domains = ["cima.ma", "www.cima.ma"]
    currency = "MAD"
    language = "fr"
    BASE_URL = "https://cima.ma/wp-json/wc/store/v1/products"
