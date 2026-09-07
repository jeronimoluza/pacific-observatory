"""Vinh Hoa Vietnam health and supplement Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class VinhHoaHealthVnSpider(ShopifyBaseSpider):
    name = "vinhhoa_health_vn"
    allowed_domains = ["vinhhoa-health.com"]
    base_url = "https://vinhhoa-health.com"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
