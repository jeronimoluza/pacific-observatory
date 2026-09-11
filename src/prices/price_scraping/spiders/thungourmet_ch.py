"""Thun Gourmet (Switzerland) delicatessen — https://www.thungourmet.ch"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ThungourmetChSpider(ShopifyBaseSpider):
    name = "thungourmet_ch"
    allowed_domains = ["thungourmet.ch"]
    base_url = "https://www.thungourmet.ch"
    currency = "CHF"
    language = "de"
