"""Blade Philippines auto accessories and consumer specialty goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BladePhSpider(ShopifyBaseSpider):
    name = "blade_ph"
    allowed_domains = ["blade.ph"]
    base_url = "https://blade.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
