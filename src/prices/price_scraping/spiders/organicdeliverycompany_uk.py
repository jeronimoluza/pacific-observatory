"""Organic Delivery Company (UK) — https://organicdeliverycompany.co.uk/. Shopify storefront."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class OrganicdeliverycompanyUkSpider(ShopifyBaseSpider):
    name = "organicdeliverycompany_uk"
    allowed_domains = ["organicdeliverycompany.co.uk"]
    base_url = "https://organicdeliverycompany.co.uk"
    currency = "GBP"
    language = "en"
