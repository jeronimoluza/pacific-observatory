"""Toy Kingdom Philippines toys and games Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ToykingdomPhSpider(ShopifyBaseSpider):
    name = "toykingdom_ph"
    allowed_domains = ["www.toykingdom.com.ph", "toykingdom.com.ph"]
    base_url = "https://www.toykingdom.com.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
