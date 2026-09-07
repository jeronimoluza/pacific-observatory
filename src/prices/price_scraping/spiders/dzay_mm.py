"""Spider for DZay Myanmar."""

from ._shopify_base import ShopifyBaseSpider


class DzayMmSpider(ShopifyBaseSpider):
    name = "dzay_mm"
    allowed_domains = ["dzay.com.mm", "www.dzay.com.mm"]
    base_url = "https://dzay.com.mm"
    currency = "MMK"
    language = "en"
