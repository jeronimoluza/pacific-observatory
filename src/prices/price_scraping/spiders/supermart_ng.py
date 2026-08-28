"""Supermart.ng (Nigeria, Lagos, Shopify) — https://supermart.ng/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class SupermartNgSpider(ShopifyBaseSpider):
    name = "supermart_ng"
    allowed_domains = ["supermart.ng"]
    base_url = "https://supermart.ng"
    currency = "NGN"
    language = "en"
