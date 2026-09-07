"""Tapioca Delight PNG WooCommerce prepared-food storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class TapiocaDelightPgSpider(WooBaseSpider):
    name = "tapioca_delight_pg"
    allowed_domains = ["tapiocadelightpng.com", "www.tapiocadelightpng.com"]
    BASE_URL = "https://www.tapiocadelightpng.com/wp-json/wc/store/products"
    currency = "PGK"
    language = "en"

    def _item(self, product: dict):
        item = super()._item(product)
        if not item:
            return None
        name = item["product_name"].strip().lower()
        try:
            price = float(item["price"])
        except (TypeError, ValueError):
            price = 0.0
        if name in {"pay for quote", "test"} or item["category"] == "Quote" or price <= 0:
            return None
        return item
