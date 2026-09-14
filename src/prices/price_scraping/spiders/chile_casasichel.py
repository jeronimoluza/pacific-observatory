"""Extract positive CLP products from Casa Sichel's public Store API."""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape

import scrapy


URL = "https://casasichel.com/wp-json/wc/store/v1/products?per_page=100"


class ChileCasasichelSpider(scrapy.Spider):
    name = "chile_casasichel"
    allowed_domains = ["casasichel.com"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request(URL)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in response.json():
            prices = product.get("prices") or {}
            raw_price = prices.get("price")
            try:
                if int(raw_price) <= 0 or prices.get("currency_minor_unit") != 0:
                    continue
            except (TypeError, ValueError):
                continue
            product_id = product.get("id")
            name = unescape((product.get("name") or "").strip())
            url = product.get("permalink")
            if not (product_id and name and url and prices.get("currency_code") == "CLP"):
                continue
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "price": str(raw_price),
                "currency": "CLP",
                "channel": "other",
                "country": "Chile",
                "sector": "consumer_goods",
                "url": url,
                "in_stock": bool(product.get("is_in_stock")),
                "stock_state": (product.get("stock_availability") or {}).get("class"),
                "scraped_at_utc": scraped_at,
            }
