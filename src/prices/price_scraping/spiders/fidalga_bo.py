"""Fidalga (Bolivia, Shopify — CSV claimed Custom, actually Shopify) — https://www.fidalga.com/"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class FidalgaBoSpider(ShopifyBaseSpider):
    name = "fidalga_bo"
    allowed_domains = ["fidalga.com"]
    base_url = "https://www.fidalga.com"
    currency = "BOB"
    language = "es"
