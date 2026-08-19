"""Farmacorp (Bolivia, Shopify — CSV claimed VTEX, actually Shopify) — https://www.farmacorp.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class FarmacorpBoSpider(ShopifyBaseSpider):
    name = "farmacorp_bo"
    allowed_domains = ["farmacorp.com"]
    base_url = "https://www.farmacorp.com"
    currency = "BOB"
    language = "es"
