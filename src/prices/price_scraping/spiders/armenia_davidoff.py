"""Scrape Davidoff Armenia's public WooCommerce Store API."""

from datetime import datetime, timezone

import scrapy


class ArmeniaDavidoffSpider(scrapy.Spider):
    name = "armenia_davidoff"
    allowed_domains = ["davidoffcigars.am"]
    start_urls = [
        "https://davidoffcigars.am/wp-json/wc/store/v1/products?per_page=100"
    ]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in response.json():
            prices = product.get("prices") or {}
            product_id = product.get("id")
            name = (product.get("name") or "").strip()
            url = product.get("permalink")
            raw_price = prices.get("price")
            if not (product_id and name and url and raw_price):
                continue
            if prices.get("currency_code") != "AMD":
                continue
            try:
                minor_unit = int(prices.get("currency_minor_unit") or 0)
                amount = int(raw_price) / (10 ** minor_unit)
            except (TypeError, ValueError):
                continue
            if amount <= 0:
                continue
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "price": format(amount, ".2f").rstrip("0").rstrip("."),
                "currency": "AMD",
                "country": "Armenia",
                "category": "tobacco_and_smoking_accessories",
                "available": product.get("is_in_stock", True),
                "url": url,
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
