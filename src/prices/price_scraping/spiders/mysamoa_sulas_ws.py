"""My Samoa Sula's Supermarket and Bakery collection."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MySamoaSulasWsSpider(ShopifyBaseSpider):
    name = "mysamoa_sulas_ws"
    allowed_domains = ["mysamoa.co", "www.mysamoa.co"]
    base_url = "https://www.mysamoa.co"
    currency = "NZD"
    language = "en"
    PRODUCTS_PATH = "/collections/sula-s-supermarket-bakery/products.json"
