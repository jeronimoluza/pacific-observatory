"""Allomama Brunei maternity and baby Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class AllomamaBnSpider(ShopifyBaseSpider):
    name = "allomama_bn"
    allowed_domains = ["allomama-bn.com"]
    base_url = "https://allomama-bn.com"
    currency = "BND"
    language = "en"
