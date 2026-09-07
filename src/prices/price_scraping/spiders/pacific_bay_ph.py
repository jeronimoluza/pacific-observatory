"""Pacific Bay Philippines seafood Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PacificBayPhSpider(ShopifyBaseSpider):
    name = "pacific_bay_ph"
    allowed_domains = ["pacificbay.com.ph", "www.pacificbay.com.ph"]
    base_url = "https://www.pacificbay.com.ph"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
