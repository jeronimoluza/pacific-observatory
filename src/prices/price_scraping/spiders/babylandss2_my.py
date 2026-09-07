"""Babyland SS2 Malaysia baby goods Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class BabylandSs2MySpider(ShopifyBaseSpider):
    name = "babylandss2_my"
    allowed_domains = ["babylandss2.com", "www.babylandss2.com"]
    base_url = "https://babylandss2.com"
    currency = "MYR"
    language = "en"
