"""Atea Store Tahiti hardware / tools WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class AteaStorePfSpider(WooBaseSpider):
    name = "atea_store_pf"
    allowed_domains = ["atea-store.pf"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://atea-store.pf/wp-json/wc/store/v1/products"
