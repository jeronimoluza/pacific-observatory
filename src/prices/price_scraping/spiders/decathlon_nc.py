"""Decathlon New Caledonia sporting goods Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class DecathlonNcSpider(ShopifyBaseSpider):
    name = "decathlon_nc"
    allowed_domains = ["decathlon.nc"]
    base_url = "https://decathlon.nc"
    currency = "XPF"
    language = "fr"
