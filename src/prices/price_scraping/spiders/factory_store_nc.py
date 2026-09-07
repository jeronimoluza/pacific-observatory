"""Factory Store New Caledonia apparel WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class FactoryStoreNcSpider(WooBaseSpider):
    name = "factory_store_nc"
    allowed_domains = ["factorystore.nc", "www.factorystore.nc"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://www.factorystore.nc/wp-json/wc/store/v1/products"
