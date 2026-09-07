"""Mandaue Foam Philippines furniture, lighting, and home goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MandauefoamPhSpider(ShopifyBaseSpider):
    name = "mandauefoam_ph"
    allowed_domains = ["mandauefoam.ph"]
    base_url = "https://mandauefoam.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
