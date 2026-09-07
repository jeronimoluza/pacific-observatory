"""Mmmm! Singapore grocery storefront via Shopify products JSON."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MmmmSgSpider(ShopifyBaseSpider):
    name = "mmmm_sg"
    allowed_domains = ["mmmm.com.sg"]
    base_url = "https://mmmm.com.sg"
    currency = "SGD"
    language = "en"
