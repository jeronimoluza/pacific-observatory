"""Toyworld New Zealand toys and games Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ToyworldNzSpider(ShopifyBaseSpider):
    name = "toyworld_nz"
    allowed_domains = ["www.toyworld.co.nz"]
    base_url = "https://www.toyworld.co.nz"
    currency = "NZD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
