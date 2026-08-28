"""GROX / Migross (Mauritania, Shopify) — https://groxmarket.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class GroxmarketSpider(ShopifyBaseSpider):
    name = "groxmarket"
    allowed_domains = ["groxmarket.com"]
    base_url = "https://groxmarket.com"
    currency = "MRU"
    language = "fr"
