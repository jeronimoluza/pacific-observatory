"""SSAB Samoa Shopify storefront."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class SsabWsSpider(ShopifyBaseSpider):
    name = "ssab_ws"
    allowed_domains = ["ssab.ws"]
    base_url = "https://ssab.ws"
    currency = "NZD"
    language = "en"

    def _items(self, product: dict):
        for item in super()._items(product) or []:
            category = str(item.get("category") or "").lower()
            name = str(item.get("product_name") or "").lower()
            if category == "food" or any(
                token in name
                for token in (
                    "flour",
                    "mayo",
                    "rice",
                    "corn",
                    "cereal",
                    "sugar",
                    "beef",
                    "chicken",
                    "pepsi",
                    "coffee",
                )
            ):
                yield item
