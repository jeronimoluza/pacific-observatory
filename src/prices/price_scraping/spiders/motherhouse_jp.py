"""Motherhouse Japan fashion and bag Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MotherhouseJpSpider(ShopifyBaseSpider):
    name = "motherhouse_jp"
    allowed_domains = ["www.mother-house.jp"]
    base_url = "https://www.mother-house.jp"
    currency = "JPY"
    language = "ja"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
