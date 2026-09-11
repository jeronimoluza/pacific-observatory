"""Hap Sang Hong (Macao) baking and dry-goods wholesaler — https://hapsanghong.com. WooCommerce Store API."""

from price_scraping.spiders._woo_base import WooBaseSpider


class HapsanghongMoSpider(WooBaseSpider):
    name = "hapsanghong_mo"
    allowed_domains = ["hapsanghong.com"]
    currency = "MOP"
    language = "zh"
    BASE_URL = "https://hapsanghong.com/wp-json/wc/store/v1/products"
