"""Re.juve Indonesia beverage Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class RejuveIdSpider(ShopifyBaseSpider):
    name = "rejuve_id"
    allowed_domains = ["rejuve.co.id"]
    base_url = "https://rejuve.co.id"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
