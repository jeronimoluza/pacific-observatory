"""Kapok Hong Kong fashion, accessories, and lifestyle Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class KapokHkSpider(ShopifyBaseSpider):
    name = "kapok_hk"
    allowed_domains = ["ka-pok.com"]
    base_url = "https://ka-pok.com"
    currency = "HKD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}

