"""Nutrimart Indonesia Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class NutrimartIdSpider(ShopifyBaseSpider):
    name = "nutrimart_id"
    allowed_domains = ["nutrimart.co.id"]
    base_url = "https://nutrimart.co.id"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
