"""Rare Food Shop Philippines Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class RareFoodShopPhSpider(ShopifyBaseSpider):
    name = "rare_food_shop_ph"
    allowed_domains = ["rarefoodshop.com"]
    base_url = "https://rarefoodshop.com"
    currency = "PHP"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
