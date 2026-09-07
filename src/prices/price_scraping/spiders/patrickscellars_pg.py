"""Patricks Cellars PNG Shopify beverage storefront."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PatricksCellarsPgSpider(ShopifyBaseSpider):
    name = "patrickscellars_pg"
    allowed_domains = ["patrickscellars.com", "www.patrickscellars.com"]
    base_url = "https://www.patrickscellars.com"
    PRODUCTS_PATH = "/collections/all/products.json"
    currency = "PGK"
    language = "en"
