"""Mantra Foods (Mauritius, organic/shelf-stable, Shopify) — https://mantrafoods.mu/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MantrafoodsMuSpider(ShopifyBaseSpider):
    name = "mantrafoods_mu"
    allowed_domains = ["mantrafoods.mu"]
    base_url = "https://mantrafoods.mu"
    currency = "MUR"
    language = "en"
