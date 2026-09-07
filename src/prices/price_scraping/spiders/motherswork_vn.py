"""Motherswork Vietnam baby goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MothersworkVnSpider(ShopifyBaseSpider):
    name = "motherswork_vn"
    allowed_domains = ["www.motherswork.com.vn", "motherswork.com.vn"]
    base_url = "https://www.motherswork.com.vn"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
