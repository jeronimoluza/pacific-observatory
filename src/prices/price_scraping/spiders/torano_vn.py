"""Torano Vietnam apparel Haravan/Shopify-compatible catalog feed."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ToranoVnSpider(ShopifyBaseSpider):
    name = "torano_vn"
    allowed_domains = ["torano.vn"]
    base_url = "https://torano.vn"
    PRODUCTS_PATH = "/collections/all/products.json"
    currency = "VND"
    language = "vi"
    custom_settings = {**ShopifyBaseSpider.custom_settings, "COOKIES_ENABLED": False}
