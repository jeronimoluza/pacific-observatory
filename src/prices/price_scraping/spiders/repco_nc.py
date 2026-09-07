"""Repco New Caledonia auto parts/accessories WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class RepcoNcSpider(WooBaseSpider):
    name = "repco_nc"
    allowed_domains = ["repco.nc"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://repco.nc/wp-json/wc/store/v1/products"
