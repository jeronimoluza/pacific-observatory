"""Konzoom (Ghana, Shopify) — https://konzoom.shop/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class KonzoomSpider(ShopifyBaseSpider):
    name = "konzoom"
    allowed_domains = ["konzoom.shop"]
    base_url = "https://konzoom.shop"
    currency = "GHS"
    language = "en"
