"""Pacific Island Trade / K&K Majuro (Marshall Islands) Shopify collection."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class PacificIslandTradeMhSpider(ShopifyBaseSpider):
    name = "pacificislandtrade_mh"
    allowed_domains = ["pacificislandtrade.com"]
    base_url = "https://pacificislandtrade.com"
    PRODUCTS_PATH = "/collections/majuro-k-k-store/products.json"
    currency = "USD"
    language = "en"

    def _items(self, product: dict):
        for item in super()._items(product) or []:
            name = item.get("product_name") or ""
            if "gift certificate" in name.lower():
                continue
            item["category"] = item.get("category") or "K&K Majuro Store"
            yield item
