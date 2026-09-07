"""Courts PNG WooCommerce furniture, appliance, and electronics storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class CourtsPngPgSpider(WooBaseSpider):
    name = "courts_png_pg"
    allowed_domains = ["courts.com.pg", "www.courts.com.pg"]
    BASE_URL = "https://courts.com.pg/wp-json/wc/store/products"
    currency = "PGK"
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
