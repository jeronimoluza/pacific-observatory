"""Supersports Vietnam sports apparel and footwear Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class SupersportsVnSpider(ShopifyBaseSpider):
    name = "supersports_vn"
    allowed_domains = ["supersports.com.vn", "www.supersports.com.vn"]
    base_url = "https://supersports.com.vn"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
