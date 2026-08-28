"""Farmacias Arrocha (Panama) -- https://arrocha.com/. Drugstore chain
webshop (personal care, cosmetics, food, toys, office). Shopify catalog is
open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ArrochaPaSpider(ShopifyBaseSpider):
    name = "arrocha_pa"
    allowed_domains = ["arrocha.com"]
    base_url = "https://arrocha.com"
    currency = "USD"
    language = "es"
