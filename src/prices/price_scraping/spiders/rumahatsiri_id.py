"""Rumah Atsiri Indonesia personal-care Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class RumahatsiriIdSpider(ShopifyBaseSpider):
    name = "rumahatsiri_id"
    allowed_domains = ["shop.rumahatsiri.com"]
    base_url = "https://shop.rumahatsiri.com"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
