"""Pacific Sales Fiji food and drink collection."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PacificSalesFjSpider(ShopifyBaseSpider):
    name = "pacificsales_fj"
    allowed_domains = ["pacificsales.shop"]
    base_url = "https://pacificsales.shop"
    currency = "FJD"
    language = "en"
    PRODUCTS_PATH = "/collections/food-drink/products.json"
