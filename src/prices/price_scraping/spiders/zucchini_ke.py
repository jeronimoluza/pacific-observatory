"""Zucchini Food Market (Kenya, Shopify) — https://zucchini.co.ke/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ZucchiniKeSpider(ShopifyBaseSpider):
    name = "zucchini_ke"
    allowed_domains = ["zucchini.co.ke"]
    base_url = "https://zucchini.co.ke"
    currency = "KES"
    language = "en"
