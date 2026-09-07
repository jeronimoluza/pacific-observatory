"""MR DIY Malaysia hardware, household, and small electronics Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MrDiyMySpider(ShopifyBaseSpider):
    name = "mrdiy_my"
    allowed_domains = ["mrdiy.com.my", "www.mrdiy.com.my"]
    base_url = "https://mrdiy.com.my"
    currency = "MYR"
    language = "en"
