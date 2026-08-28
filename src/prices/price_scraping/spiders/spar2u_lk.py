"""SPAR2U Sri Lanka (Shopify) — https://spar2u.lk/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class Spar2uLkSpider(ShopifyBaseSpider):
    name = "spar2u_lk"
    allowed_domains = ["spar2u.lk"]
    base_url = "https://spar2u.lk"
    currency = "LKR"
    language = "en"
