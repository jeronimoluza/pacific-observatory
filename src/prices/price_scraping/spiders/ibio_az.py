"""iBio (Azerbaijan) organic/health grocery — https://ibio.az"""

from price_scraping.spiders._shopify_base import ShopifyBaseSpider


class IbioAzSpider(ShopifyBaseSpider):
    name = "ibio_az"
    allowed_domains = ["ibio.az"]
    base_url = "https://ibio.az"
    currency = "AZN"
    language = "az"
