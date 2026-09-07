"""Boardriders New Caledonia apparel and footwear Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BoardridersNcSpider(ShopifyBaseSpider):
    name = "boardriders_nc"
    allowed_domains = ["boardriders.nc"]
    base_url = "https://boardriders.nc"
    currency = "XPF"
    language = "fr"
