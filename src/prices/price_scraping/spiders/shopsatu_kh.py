"""Spider for SATU Cambodia."""

from ._shopify_base import ShopifyBaseSpider


class ShopsatuKhSpider(ShopifyBaseSpider):
    name = "shopsatu_kh"
    allowed_domains = ["shopsatu.com", "www.shopsatu.com"]
    base_url = "https://shopsatu.com"
    currency = "USD"
    language = "en"
