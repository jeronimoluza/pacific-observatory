"""Cityluxe Singapore stationery and writing supplies Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class CityluxeSgSpider(ShopifyBaseSpider):
    name = "cityluxe_sg"
    allowed_domains = ["cityluxe.sg", "www.cityluxe.sg"]
    base_url = "https://cityluxe.sg"
    currency = "SGD"
    language = "en"
