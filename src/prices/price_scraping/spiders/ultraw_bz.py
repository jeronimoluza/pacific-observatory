"""Ultraw (Belize) — https://ultraw.bz/. Multi-vendor WooCommerce marketplace."""

from price_scraping.spiders._woo_base import WooBaseSpider


class UltrawBzSpider(WooBaseSpider):
    name = "ultraw_bz"
    allowed_domains = ["ultraw.bz"]
    currency = "BZD"
    language = "en"
    BASE_URL = "https://ultraw.bz/wp-json/wc/store/v1/products"
