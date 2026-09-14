"""Consumer-product listings from Habanos La Tabaqueria's public Store API."""

from __future__ import annotations

import html
from datetime import datetime, timezone

import scrapy


class ColombiaHabanosLaTabaqueriaSpider(scrapy.Spider):
    name = "colombia_habanoslatabaqueria"
    allowed_domains = ["habanoslatabaqueria.com.co", "www.habanoslatabaqueria.com.co"]
    start_urls = [
        "https://www.habanoslatabaqueria.com.co/wp-json/wc/store/v1/products?per_page=100"
    ]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in response.json():
            prices = product.get("prices") or {}
            raw_price = prices.get("price")
            if prices.get("currency_code") != "COP":
                continue
            try:
                minor_unit = int(prices.get("currency_minor_unit"))
                amount = int(raw_price) / (10 ** minor_unit)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            product_id = product.get("id")
            name = html.unescape((product.get("name") or "").strip())
            url = product.get("permalink")
            if not product_id or not name or not url or amount <= 0:
                continue
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "price": format(amount, ".2f").rstrip("0").rstrip("."),
                "currency": "COP",
                "country": "Colombia",
                "category": "tobacco_and_smoking_accessories",
                "available": bool(product.get("is_in_stock", False)),
                "url": url,
                "language": "es",
                "scraped_at_utc": scraped_at,
            }
