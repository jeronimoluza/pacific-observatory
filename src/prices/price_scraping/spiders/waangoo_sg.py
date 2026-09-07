"""Waangoo Singapore grocery storefront via Shopify products JSON."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class WaangooSgSpider(ShopifyBaseSpider):
    name = "waangoo_sg"
    allowed_domains = ["www.waangoo.com", "waangoo.com"]
    base_url = "https://www.waangoo.com"
    currency = "SGD"
    language = "en"
