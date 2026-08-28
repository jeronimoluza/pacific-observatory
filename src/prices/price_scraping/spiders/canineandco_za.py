"""Canine & Co (South Africa, Shopify) — https://canineandco.co.za/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class CanineandcoZaSpider(ShopifyBaseSpider):
    name = "canineandco_za"
    allowed_domains = ["canineandco.co.za"]
    base_url = "https://canineandco.co.za"
    currency = "ZAR"
    language = "en"
