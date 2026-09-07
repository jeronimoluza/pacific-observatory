"""Mykingdom Vietnam toys and games Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MykingdomVnSpider(ShopifyBaseSpider):
    name = "mykingdom_vn"
    allowed_domains = ["www.mykingdom.com.vn", "mykingdom.com.vn"]
    base_url = "https://www.mykingdom.com.vn"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
