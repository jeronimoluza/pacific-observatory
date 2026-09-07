"""Fiji Traders Shopify computers and electronics storefront."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class FijiTradersFjSpider(ShopifyBaseSpider):
    name = "fiji_traders_fj"
    allowed_domains = ["fijitraders.com", "www.fijitraders.com"]
    base_url = "https://fijitraders.com"
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
