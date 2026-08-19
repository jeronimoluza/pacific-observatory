"""Biltong Boytjies (South Africa, Shopify) — https://biltongboytjies.co.za/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class BiltongboytjiesZaSpider(ShopifyBaseSpider):
    name = "biltongboytjies_za"
    allowed_domains = ["biltongboytjies.co.za"]
    base_url = "https://biltongboytjies.co.za"
    currency = "ZAR"
    language = "en"
