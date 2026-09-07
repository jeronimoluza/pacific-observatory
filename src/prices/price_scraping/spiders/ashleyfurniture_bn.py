"""Ashley Furniture Brunei Shopify catalog."""

from __future__ import annotations

from ._shopify_base import ShopifyBaseSpider


class AshleyFurnitureBnSpider(ShopifyBaseSpider):
    name = "ashleyfurniture_bn"
    allowed_domains = ["store.ashleyfurniture.com.bn"]
    base_url = "https://store.ashleyfurniture.com.bn"
    currency = "BND"
    language = "en"
