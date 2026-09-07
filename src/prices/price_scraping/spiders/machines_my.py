"""Machines Malaysia Apple electronics Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MachinesMySpider(ShopifyBaseSpider):
    name = "machines_my"
    allowed_domains = ["machines.com.my", "www.machines.com.my"]
    base_url = "https://www.machines.com.my"
    currency = "MYR"
    language = "en"
