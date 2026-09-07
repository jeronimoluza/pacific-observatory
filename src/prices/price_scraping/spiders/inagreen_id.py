"""Inagreen Indonesia fresh produce Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class InagreenIdSpider(ShopifyBaseSpider):
    name = "inagreen_id"
    allowed_domains = ["inagreenid.com"]
    base_url = "https://inagreenid.com"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
