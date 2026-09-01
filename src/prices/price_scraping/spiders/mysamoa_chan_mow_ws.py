"""My Samoa Chan Mow Supermarket collection."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class MySamoaChanMowWsSpider(ShopifyBaseSpider):
    name = "mysamoa_chan_mow_ws"
    allowed_domains = ["mysamoa.co", "www.mysamoa.co"]
    base_url = "https://www.mysamoa.co"
    currency = "NZD"
    language = "en"
    PRODUCTS_PATH = "/collections/chan-mow-supermarket/products.json"
