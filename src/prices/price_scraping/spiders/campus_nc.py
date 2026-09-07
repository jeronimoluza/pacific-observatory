"""Campus New Caledonia footwear Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class CampusNcSpider(ShopifyBaseSpider):
    name = "campus_nc"
    allowed_domains = ["campus.nc"]
    base_url = "https://campus.nc"
    currency = "XPF"
    language = "fr"
