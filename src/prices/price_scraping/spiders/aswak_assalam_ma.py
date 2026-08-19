"""Aswak Assalam (Morocco) — https://www.aswakassalam.com/. Full-line WooCommerce hypermarket."""

from price_scraping.spiders._woo_base import WooBaseSpider


class AswakAssalamMaSpider(WooBaseSpider):
    name = "aswak_assalam_ma"
    allowed_domains = ["aswakassalam.com", "www.aswakassalam.com"]
    currency = "MAD"
    language = "fr"
    BASE_URL = "https://www.aswakassalam.com/wp-json/wc/store/v1/products"
