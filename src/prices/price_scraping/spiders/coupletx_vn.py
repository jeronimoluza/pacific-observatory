"""Couple TX Vietnam apparel Shopify collection feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class CoupletxVnSpider(ShopifyBaseSpider):
    name = "coupletx_vn"
    allowed_domains = ["coupletx.com"]
    base_url = "https://coupletx.com"
    PRODUCTS_PATH = "/collections/all/products.json"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
