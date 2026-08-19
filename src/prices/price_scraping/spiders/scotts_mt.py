"""Scotts Supermarket (Malta) — https://www.scotts.com.mt/. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class ScottsMtSpider(WooBaseSpider):
    name = "scotts_mt"
    allowed_domains = ["scotts.com.mt", "www.scotts.com.mt"]
    currency = "EUR"
    language = "en"
    BASE_URL = "https://www.scotts.com.mt/wp-json/wc/store/v1/products"
