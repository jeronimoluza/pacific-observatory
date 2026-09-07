"""Healthy Options Philippines Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class HealthyOptionsPhSpider(ShopifyBaseSpider):
    name = "healthy_options_ph"
    allowed_domains = ["shop.healthyoptions.com.ph"]
    base_url = "https://shop.healthyoptions.com.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
