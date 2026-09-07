"""Toys R Us Australia toys and baby goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ToysrusAuSpider(ShopifyBaseSpider):
    name = "toysrus_au"
    allowed_domains = ["www.toysrus.com.au"]
    base_url = "https://www.toysrus.com.au"
    currency = "AUD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
