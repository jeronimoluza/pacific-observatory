"""Prouds Fiji Shopify department-store catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class ProudsFjSpider(ShopifyBaseSpider):
    name = "prouds_fj"
    allowed_domains = ["shop.prouds.com.fj"]
    base_url = "https://shop.prouds.com.fj"
    currency = "FJD"
    language = "en"

    def _items(self, product: dict):
        for item in super()._items(product) or []:
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            yield item
