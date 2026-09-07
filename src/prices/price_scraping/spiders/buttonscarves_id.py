"""Buttonscarves Indonesia bags, apparel, and accessories Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ButtonscarvesIdSpider(ShopifyBaseSpider):
    name = "buttonscarves_id"
    allowed_domains = ["buttonscarves.com", "www.buttonscarves.com"]
    base_url = "https://www.buttonscarves.com"
    currency = "IDR"
    language = "id"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
