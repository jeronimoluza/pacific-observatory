"""PAKLEIMO Macao furniture Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PakleimoMoSpider(ShopifyBaseSpider):
    name = "pakleimo_mo"
    allowed_domains = ["www.pakleimo.com"]
    base_url = "https://www.pakleimo.com"
    currency = "MOP"
    language = "zh-Hant"

    def _items(self, p: dict):
        for item in super()._items(p):
            item["category"] = item.get("category") or "Furniture and home goods"
            yield item
