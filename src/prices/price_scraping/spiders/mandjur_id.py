"""Apotek Mandjur Indonesia Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MandjurIdSpider(ShopifyBaseSpider):
    name = "mandjur_id"
    allowed_domains = ["www.mandjur.co.id", "mandjur.co.id"]
    base_url = "https://www.mandjur.co.id"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
