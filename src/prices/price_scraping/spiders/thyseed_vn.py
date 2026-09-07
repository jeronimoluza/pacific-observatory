"""Thyseed Vietnam baby-feeding goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ThyseedVnSpider(ShopifyBaseSpider):
    name = "thyseed_vn"
    allowed_domains = ["thyseed.vn"]
    base_url = "https://thyseed.vn"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
