"""HealthPost New Zealand natural health and personal-care Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class HealthpostNzSpider(ShopifyBaseSpider):
    name = "healthpost_nz"
    allowed_domains = ["www.healthpost.co.nz"]
    base_url = "https://www.healthpost.co.nz"
    currency = "NZD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

