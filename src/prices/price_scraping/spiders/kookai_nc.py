"""Kookai New Caledonia apparel Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class KookaiNcSpider(ShopifyBaseSpider):
    name = "kookai_nc"
    allowed_domains = ["kookai.nc", "www.kookai.nc"]
    base_url = "https://www.kookai.nc"
    currency = "XPF"
    language = "fr"
