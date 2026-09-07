"""Challenger Singapore electronics Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class ChallengerSgSpider(ShopifyBaseSpider):
    name = "challenger_sg"
    allowed_domains = ["challenger.sg", "online.challenger.sg"]
    base_url = "https://online.challenger.sg"
    currency = "SGD"
    language = "en"
