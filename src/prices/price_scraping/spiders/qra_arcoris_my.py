"""Qra Arcoris Malaysia grocery storefront via Shopify products JSON."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class QraArcorisMySpider(ShopifyBaseSpider):
    name = "qra_arcoris_my"
    allowed_domains = ["arcoris.qrafoods.com"]
    base_url = "https://arcoris.qrafoods.com"
    currency = "MYR"
    language = "en"
