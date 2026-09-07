"""Citiesocial Taiwan home, lifestyle, and electronics Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class CitiesocialTwSpider(ShopifyBaseSpider):
    name = "citiesocial_tw"
    allowed_domains = ["www.citiesocial.com"]
    base_url = "https://www.citiesocial.com"
    currency = "TWD"
    language = "zh"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
