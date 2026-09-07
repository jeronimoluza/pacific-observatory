"""Smiths City New Zealand furniture and appliance Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class SmithscityNzSpider(ShopifyBaseSpider):
    name = "smithscity_nz"
    allowed_domains = ["www.smithscity.co.nz"]
    base_url = "https://www.smithscity.co.nz"
    currency = "NZD"
    language = "en"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
