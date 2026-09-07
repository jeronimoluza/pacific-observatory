"""Baby Central Hong Kong baby goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BabycentralHkSpider(ShopifyBaseSpider):
    name = "babycentral_hk"
    allowed_domains = ["babycentral.com.hk"]
    base_url = "https://babycentral.com.hk"
    currency = "HKD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
