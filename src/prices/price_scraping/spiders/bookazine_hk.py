"""Bookazine Hong Kong books, stationery, toys, and gifts Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BookazineHkSpider(ShopifyBaseSpider):
    name = "bookazine_hk"
    allowed_domains = ["bookazine.com.hk"]
    base_url = "https://bookazine.com.hk"
    currency = "HKD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

