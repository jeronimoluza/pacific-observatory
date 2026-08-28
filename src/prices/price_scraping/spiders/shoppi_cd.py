"""Shoppi / S&K (DR Congo, Shopify) — https://www.shoppi.cd/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ShoppiCdSpider(ShopifyBaseSpider):
    name = "shoppi_cd"
    allowed_domains = ["shoppi.cd"]
    base_url = "https://www.shoppi.cd"
    currency = "CDF"
    language = "en"
