"""Pacific Island Trade / Lei-Side Chuuk (FSM) Shopify rows."""

from __future__ import annotations

import re

from ._shopify_base import ShopifyBaseSpider

_PREFIX_RE = re.compile(r"^\(LS CHUUK\)\s*", re.I)


class PacificIslandTradeFmSpider(ShopifyBaseSpider):
    name = "pacificislandtrade_fm"
    allowed_domains = ["pacificislandtrade.com"]
    base_url = "https://pacificislandtrade.com"
    currency = "USD"
    language = "en"

    def _items(self, product: dict):
        title = product.get("title") or ""
        if not _PREFIX_RE.search(title):
            return
        for item in super()._items(product) or []:
            name = item.get("product_name") or ""
            if "gift certificate" in name.lower():
                continue
            item["product_name"] = _PREFIX_RE.sub("", name).strip()
            item["category"] = item.get("category") or "Lei-Side Chuuk Store"
            yield item
