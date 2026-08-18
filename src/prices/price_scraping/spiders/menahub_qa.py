"""MenaHub (Qatar) -- https://menahub.com/. General household/appliance
retailer sourced from multiple trading companies. Shopify catalog is open."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MenahubQaSpider(ShopifyBaseSpider):
    name = "menahub_qa"
    allowed_domains = ["menahub.com"]
    base_url = "https://menahub.com"
    currency = "QAR"
    language = "en"
