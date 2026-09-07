"""King Sports New Caledonia sportswear Shopify feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class KingSportsNcSpider(ShopifyBaseSpider):
    name = "kingsports_nc"
    allowed_domains = ["kingsports.nc"]
    base_url = "https://kingsports.nc"
    currency = "XPF"
    language = "fr"
