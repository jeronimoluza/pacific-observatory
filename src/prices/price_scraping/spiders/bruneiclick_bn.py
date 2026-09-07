"""Brunei Click electronics and games Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BruneiClickBnSpider(ShopifyBaseSpider):
    name = "bruneiclick_bn"
    allowed_domains = ["www.bruneiclick.com"]
    base_url = "https://www.bruneiclick.com"
    currency = "BND"
    language = "en"
