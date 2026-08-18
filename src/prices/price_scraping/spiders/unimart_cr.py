"""Unimart (Costa Rica) -- https://unimart.com/. Consumer electronics and
general merchandise retailer. Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class UnimartCrSpider(ShopifyBaseSpider):
    name = "unimart_cr"
    allowed_domains = ["unimart.com"]
    base_url = "https://unimart.com"
    currency = "CRC"
    language = "es"
