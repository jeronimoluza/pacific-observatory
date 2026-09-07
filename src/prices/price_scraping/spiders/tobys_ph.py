"""Toby's Sports Philippines sports goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class TobysPhSpider(ShopifyBaseSpider):
    name = "tobys_ph"
    allowed_domains = ["www.tobys.com", "tobys.com"]
    base_url = "https://www.tobys.com"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
