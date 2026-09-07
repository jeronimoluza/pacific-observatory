"""Future Store Brunei home technology and electronics Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class FutureStoreBnSpider(ShopifyBaseSpider):
    name = "futurestore_bn"
    allowed_domains = ["www.thefuturestore.co"]
    base_url = "https://www.thefuturestore.co"
    currency = "BND"
    language = "en"
