"""IT Zone Samoa WooCommerce electronics and mobile storefront."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class ItzoneWsSpider(WooBaseSpider):
    name = "itzone_ws"
    allowed_domains = ["itzone.ws", "www.itzone.ws"]
    BASE_URL = "https://itzone.ws/wp-json/wc/store/products"
    currency = "USD"
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
