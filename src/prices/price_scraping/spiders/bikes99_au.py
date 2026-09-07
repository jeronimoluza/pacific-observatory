"""99 Bikes Australia bicycle and cycling-accessory Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class Bikes99AuSpider(ShopifyBaseSpider):
    name = "bikes99_au"
    allowed_domains = ["www.99bikes.com.au"]
    base_url = "https://www.99bikes.com.au"
    currency = "AUD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
