"""Submarina Guam online-ordering menu -- WooCommerce Store API."""

from __future__ import annotations

from ._woo_base import WooBaseSpider

_SKIP_NAMES = {"paid extras", "other charges", "misc"}


class SubmarinaGuamSpider(WooBaseSpider):
    name = "submarina_guam"
    allowed_domains = ["submarinaguam.com"]
    BASE_URL = "https://submarinaguam.com/wp-json/wc/store/v1/products"
    currency = "USD"
    language = "en"

    def _item(self, p: dict):
        item = super()._item(p)
        if not item:
            return None
        try:
            price = float(item["price"])
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        if str(item.get("product_name") or "").strip().lower() in _SKIP_NAMES:
            return None
        return item
