"""Bibo Mart Vietnam baby and family goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BibomartVnSpider(ShopifyBaseSpider):
    name = "bibomart_vn"
    allowed_domains = ["bibomartgroup.com"]
    base_url = "https://bibomartgroup.com"
    currency = "USD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
