"""Mecindo (Denmark) — https://mecindo.dk/. Shopify storefront."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MecindoDkSpider(ShopifyBaseSpider):
    name = "mecindo_dk"
    allowed_domains = ["mecindo.dk"]
    base_url = "https://mecindo.dk"
    currency = "DKK"
    language = "da"
