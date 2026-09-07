"""Rickronk Kiribati Shopify catalog."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class RickronkKiSpider(ShopifyBaseSpider):
    name = "rickronk_ki"
    allowed_domains = ["rickronk.com"]
    base_url = "https://rickronk.com"
    currency = "AUD"
    language = "en"

