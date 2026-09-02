"""Hard Rock Sokehs (Pohnpei, FSM) Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class HardRockSokehsFmSpider(ShopifyBaseSpider):
    name = "hardrocksokehs_fm"
    allowed_domains = ["hardrocksokehs.com"]
    base_url = "https://hardrocksokehs.com"
    currency = "USD"
    language = "en"

    def _items(self, product: dict):
        for item in super()._items(product) or []:
            try:
                price = float(item.get("price") or 0)
            except (TypeError, ValueError):
                price = 0
            if price <= 0:
                continue
            yield item
