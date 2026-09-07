"""Thenblank Indonesia apparel Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ThenblankIdSpider(ShopifyBaseSpider):
    name = "thenblank_id"
    allowed_domains = ["thenblank.com"]
    base_url = "https://thenblank.com"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
