"""Djórahandilin (Faroe Islands) WooCommerce storefront -- https://djor.fo/.

The country's largest animal-goods retailer. Store API open; reports DKK with
currency_minor_unit 2, which the base divides out.
"""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class DjorFoSpider(WooBaseSpider):
    name = "djor_fo"
    allowed_domains = ["djor.fo", "www.djor.fo"]
    BASE_URL = "https://djor.fo/wp-json/wc/store/v1/products"
    currency = "DKK"
    language = "fo"
