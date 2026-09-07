"""Little Retail Philippines Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class LittleRetailPhSpider(ShopifyBaseSpider):
    name = "little_retail_ph"
    allowed_domains = ["littleretailph.com"]
    base_url = "https://littleretailph.com"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
