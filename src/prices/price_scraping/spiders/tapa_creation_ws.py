"""Tapa Creation Samoa Shopify clothing and sportswear storefront."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class TapaCreationWsSpider(ShopifyBaseSpider):
    name = "tapa_creation_ws"
    allowed_domains = ["tapacreationsamoa.com", "www.tapacreationsamoa.com"]
    base_url = "https://tapacreationsamoa.com"
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
