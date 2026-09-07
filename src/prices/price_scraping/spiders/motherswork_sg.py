"""Motherswork Singapore baby, toy, and family goods Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MothersworkSgSpider(ShopifyBaseSpider):
    name = "motherswork_sg"
    allowed_domains = ["motherswork.com.sg", "www.motherswork.com.sg"]
    base_url = "https://motherswork.com.sg"
    currency = "SGD"
    language = "en"
