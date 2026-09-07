"""EveniBlock Samoa Shopify sports, apparel, and footwear catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class EveniblockWsSpider(ShopifyBaseSpider):
    name = "eveniblock_ws"
    allowed_domains = ["eveniblock.com", "www.eveniblock.com"]
    base_url = "https://eveniblock.com"
    currency = "WST"
    language = "en"

    def _items(self, product: dict):
        for item in super()._items(product) or []:
            try:
                if float(item["price"]) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            yield item
