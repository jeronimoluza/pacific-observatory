"""CJS Supermarket Fiji WooCommerce storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class CjsSupermarketFjSpider(WooBaseSpider):
    name = "cjs_supermarket_fj"
    allowed_domains = ["www.cjssupermarket.com.fj", "cjssupermarket.com.fj"]
    BASE_URL = "https://www.cjssupermarket.com.fj/wp-json/wc/store/v1/products"
    currency = "FJD"
    language = "en"
