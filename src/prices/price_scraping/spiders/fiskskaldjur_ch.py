"""Fisk & Skaldjur (Switzerland) fish and seafood — https://www.fiskskaldjur.ch"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class FiskskaldjurChSpider(ShopifyBaseSpider):
    name = "fiskskaldjur_ch"
    allowed_domains = ["fiskskaldjur.ch"]
    base_url = "https://www.fiskskaldjur.ch"
    currency = "CHF"
    language = "de"
