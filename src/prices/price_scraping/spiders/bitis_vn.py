"""Biti's Vietnam footwear and accessories Haravan/Shopify-compatible catalog feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class BitisVnSpider(ShopifyBaseSpider):
    name = "bitis_vn"
    allowed_domains = ["bitis.com.vn"]
    base_url = "https://bitis.com.vn"
    PRODUCTS_PATH = "/collections/all/products.json"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
