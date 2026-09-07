"""Informatique du Fenua computer equipment WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class IdfenuaPfSpider(WooBaseSpider):
    name = "idfenua_pf"
    allowed_domains = ["idfenua.com"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://idfenua.com/wp-json/wc/store/v1/products"
