"""Meuble2000 New Caledonia furniture WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class Meuble2000NcSpider(WooBaseSpider):
    name = "meuble2000_nc"
    allowed_domains = ["meuble2000.nc"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://meuble2000.nc/wp-json/wc/store/v1/products"
