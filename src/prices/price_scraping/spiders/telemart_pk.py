"""Telemart (Pakistan) -- https://telemart.pk/. Multi-vendor marketplace
(electronics, appliances, fashion, general goods). Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class TelemartPkSpider(ShopifyBaseSpider):
    name = "telemart_pk"
    allowed_domains = ["telemart.pk"]
    base_url = "https://telemart.pk"
    currency = "PKR"
    language = "en"
