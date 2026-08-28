"""Aone Supermarkets (Barbados, Shopify) — https://aonesupermarkets.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class AonesupermarketsSpider(ShopifyBaseSpider):
    name = "aonesupermarkets"
    allowed_domains = ["aonesupermarkets.com"]
    base_url = "https://aonesupermarkets.com"
    currency = "BBD"
    language = "en"
