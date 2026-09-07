"""Morris Hedstrom Fiji WooCommerce supermarket storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class MorrisHedstromFjSpider(WooBaseSpider):
    name = "morris_hedstrom_fj"
    allowed_domains = ["mh.com.fj", "www.mh.com.fj"]
    BASE_URL = "https://mh.com.fj/wp-json/wc/store/products"
    currency = "FJD"
    language = "en"
