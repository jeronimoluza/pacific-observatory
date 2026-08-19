"""Amarket (Bolivia, Shopify) — https://amarket.com.bo/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AmarketBoSpider(ShopifyBaseSpider):
    name = "amarket_bo"
    allowed_domains = ["amarket.com.bo"]
    base_url = "https://amarket.com.bo"
    currency = "BOB"
    language = "es"
