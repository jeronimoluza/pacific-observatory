"""Motoworld Philippines motorcycle gear and accessories Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MotoworldPhSpider(ShopifyBaseSpider):
    name = "motoworld_ph"
    allowed_domains = ["motoworld.com.ph", "www.motoworld.com.ph"]
    base_url = "https://www.motoworld.com.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
