"""Modessa Community Brunei clothing Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ModessaBnSpider(ShopifyBaseSpider):
    name = "modessa_bn"
    allowed_domains = ["modessacommunity.com"]
    base_url = "https://modessacommunity.com"
    currency = "BND"
    language = "en"
