"""BOEMI Botanicals Indonesia personal-care Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BoemiBotanicalsIdSpider(ShopifyBaseSpider):
    name = "boemi_botanicals_id"
    allowed_domains = ["boemibotanicals.com"]
    base_url = "https://boemibotanicals.com"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
