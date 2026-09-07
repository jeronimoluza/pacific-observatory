"""Slowood Hong Kong household, pantry, and personal-care Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class SlowoodHkSpider(ShopifyBaseSpider):
    name = "slowood_hk"
    allowed_domains = ["slowood.hk"]
    base_url = "https://slowood.hk"
    currency = "HKD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

