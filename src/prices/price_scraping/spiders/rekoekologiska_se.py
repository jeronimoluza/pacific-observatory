"""Reko Ekologiska (Sweden) — https://rekoekologiska.se/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class RekoekologiskaSeSpider(WooBaseSpider):
    name = "rekoekologiska_se"
    allowed_domains = ["rekoekologiska.se"]
    currency = "SEK"
    language = "sv"
    BASE_URL = "https://rekoekologiska.se/wp-json/wc/store/v1/products"
