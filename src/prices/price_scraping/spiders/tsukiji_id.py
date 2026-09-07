"""Tsukiji Indonesia food storefront Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class TsukijiIdSpider(ShopifyBaseSpider):
    name = "tsukiji_id"
    allowed_domains = ["tsukiji.id"]
    base_url = "https://tsukiji.id"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
