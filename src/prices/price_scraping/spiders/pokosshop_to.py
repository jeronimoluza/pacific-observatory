"""Poko's Shop Tonga grocery collection."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PokosShopToSpider(ShopifyBaseSpider):
    name = "pokosshop_to"
    allowed_domains = ["pokosshop.com.au", "www.pokosshop.com.au"]
    base_url = "https://www.pokosshop.com.au"
    currency = "AUD"
    language = "en"

    def _items(self, product: dict):
        for item in super()._items(product) or []:
            name = item.get("product_name") or ""
            try:
                price = float(item.get("price") or 0)
            except (TypeError, ValueError):
                price = 0
            if price <= 0 or "coming soon" in name.lower():
                continue
            yield item
