"""Ling & Sons Food Market (Aruba, Shopify) — https://shop.lingandsons.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class LingandsonsSpider(ShopifyBaseSpider):
    name = "lingandsons"
    allowed_domains = ["shop.lingandsons.com"]
    base_url = "https://shop.lingandsons.com"
    currency = "AWG"
    language = "en"
