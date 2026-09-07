"""CTE Tahiti appliances, electronics, and home goods WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class CteTahitiPfSpider(WooBaseSpider):
    name = "cte_tahiti_pf"
    allowed_domains = ["ctetahiti.com"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://ctetahiti.com/wp-json/wc/store/v1/products"

    def _item(self, p: dict):
        item = super()._item(p)
        if not item:
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        return item
