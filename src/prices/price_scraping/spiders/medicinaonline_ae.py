"""Medicina Online (UAE) -- https://medicinaonline.ae/. Online
pharmacy/supplements retailer. Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MedicinaonlineAeSpider(ShopifyBaseSpider):
    name = "medicinaonline_ae"
    allowed_domains = ["medicinaonline.ae"]
    base_url = "https://medicinaonline.ae"
    currency = "AED"
    language = "en"
