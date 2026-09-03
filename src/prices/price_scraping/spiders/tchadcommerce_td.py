"""TchadCommerce (Chad) WooCommerce marketplace storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class TchadcommerceTdSpider(WooBaseSpider):
    name = "tchadcommerce_td"
    allowed_domains = ["tchadcommerce.com", "www.tchadcommerce.com"]
    BASE_URL = "https://tchadcommerce.com/wp-json/wc/store/v1/products"
    currency = "XAF"
    language = "fr"
