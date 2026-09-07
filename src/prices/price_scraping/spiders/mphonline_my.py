"""MPH Malaysia books Shopify feed."""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class MphonlineMySpider(ShopifyBaseSpider):
    name = "mphonline_my"
    allowed_domains = ["mphonline.com", "www.mphonline.com"]
    base_url = "https://mphonline.com"
    currency = "MYR"
    language = "en"
