"""Courts Fiji WooCommerce furniture, appliance, and electronics storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class CourtsFjSpider(WooBaseSpider):
    name = "courts_fj"
    allowed_domains = ["courts.com.fj", "www.courts.com.fj"]
    BASE_URL = "https://www.courts.com.fj/wp-json/wc/store/products"
    currency = "FJD"
    language = "en"

    def _item(self, product: dict):
        item = super()._item(product)
        if not item:
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        return item
