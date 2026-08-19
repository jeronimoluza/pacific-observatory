"""Compro.bo (Bolivia, Shopify) — https://compro.bo/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ComproBoSpider(ShopifyBaseSpider):
    name = "compro_bo"
    allowed_domains = ["compro.bo"]
    base_url = "https://compro.bo"
    currency = "BOB"
    language = "es"
