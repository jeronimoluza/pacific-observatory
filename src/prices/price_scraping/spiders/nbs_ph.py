"""National Book Store Philippines books and stationery Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class NbsPhSpider(ShopifyBaseSpider):
    name = "nbs_ph"
    allowed_domains = ["nbs.com.ph"]
    base_url = "https://nbs.com.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
