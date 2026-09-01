"""Patricks Transport PNG pantry collection."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PatricksTransportPgSpider(ShopifyBaseSpider):
    name = "patricks_transport_pg"
    allowed_domains = ["patrickstransport.com", "www.patrickstransport.com"]
    base_url = "https://www.patrickstransport.com"
    PRODUCTS_PATH = "/collections/pantry/products.json"
    currency = "PGK"
    language = "en"
