"""Pacific Gallery Tahiti furniture WooCommerce feed."""

from __future__ import annotations

from ._woo_base import WooBaseSpider


class PacificGalleryPfSpider(WooBaseSpider):
    name = "pacific_gallery_pf"
    allowed_domains = ["pacificgallery.fr"]
    currency = "XPF"
    language = "fr"
    BASE_URL = "https://pacificgallery.fr/wp-json/wc/store/v1/products"
    FORCE_CURRENCY = "XPF"

    def _item(self, p: dict):
        item = super()._item(p)
        if item is None:
            return None
        try:
            if float(item["price"]) <= 0:
                return None
        except (TypeError, ValueError):
            return None
        return item
