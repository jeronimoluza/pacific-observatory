"""Bazarstore.az (Azerbaijan, Shopify) — https://bazarstore.az/en/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class BazarstoreAzSpider(ShopifyBaseSpider):
    name = "bazarstore_az"
    allowed_domains = ["bazarstore.az"]
    base_url = "https://bazarstore.az/en"
    currency = "AZN"
    language = "az"
