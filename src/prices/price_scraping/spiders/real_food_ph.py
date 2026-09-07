"""Real Food Philippines Shopify feed via the underlying myshopify host."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class RealFoodPhSpider(ShopifyBaseSpider):
    name = "real_food_ph"
    allowed_domains = ["realfoodph.myshopify.com"]
    base_url = "https://realfoodph.myshopify.com"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
