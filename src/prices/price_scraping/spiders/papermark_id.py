"""Papermark Indonesia stationery and office supplies Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PapermarkIdSpider(ShopifyBaseSpider):
    name = "papermark_id"
    allowed_domains = ["papermark.id"]
    base_url = "https://papermark.id"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
