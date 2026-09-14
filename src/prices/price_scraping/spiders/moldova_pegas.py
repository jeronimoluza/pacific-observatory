"""Scrape Pegas Moldova's public Magento product API."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import quote

import scrapy

from price_scraping.spiders._magento_base import MagentoRestBaseSpider


class MoldovaPegasSpider(MagentoRestBaseSpider):
    name = "moldova_pegas"
    allowed_domains = ["pegas.md"]
    currency = "MDL"
    language = "ro"

    BASE_URL = "https://pegas.md"
    PAGE_SIZE = 100
    MAX_PAGES = 100

    def _page_request(self, page: int):
        url = (
            f"{self.BASE_URL}/api/products"
            f"?searchCriteria%5BpageSize%5D={self.PAGE_SIZE}"
            f"&searchCriteria%5BcurrentPage%5D={page}&lng=ro"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"page": page},
            headers={"Accept": "application/json"},
        )

    @staticmethod
    def _attributes(product: dict) -> dict:
        return {
            str(item.get("attribute_code")): item.get("value")
            for item in product.get("custom_attributes") or []
            if item.get("attribute_code")
        }

    def _item(self, product: dict):
        name = " ".join(unescape(str(product.get("name") or "")).split())
        sku = str(product.get("sku") or product.get("id") or "").strip()
        try:
            price = Decimal(str(product.get("price")))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if not name or not sku or price <= 0 or product.get("status") != 1:
            return None

        attrs = self._attributes(product)
        out_of_stock = str(attrs.get("out_of_stock", "0")).strip() == "1"
        url = f"{self.BASE_URL}/api/products/{quote(sku)}?lng=ro"

        return {
            "product_id": sku,
            "product_name": name[:500],
            "category": None,
            "price": format(price, "f"),
            "currency": self.currency,
            "country": "Moldova",
            "sector": "consumer_goods",
            "available": not out_of_stock,
            "url": url,
            "language": self.language,
        }
