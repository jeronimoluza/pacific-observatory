"""Bali Bubs Indonesia baby food, baby care, and children's goods feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BaliBubsIdSpider(ShopifyBaseSpider):
    name = "bali_bubs_id"
    allowed_domains = ["balibubsstore.com"]
    base_url = "https://balibubsstore.com"
    currency = "IDR"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
