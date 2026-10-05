"""Scrape Salone E Market's public paginated product API."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


API_URL = "https://saloneemarket.com/api/products"


class SaloneEMarketSpider(scrapy.Spider):
    name = "saloneemarket"
    allowed_domains = ["saloneemarket.com"]
    start_urls = [f"{API_URL}?limit=100&offset=0"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://saloneemarket.com/products",
        },
    }

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(products, list):
            return
        try:
            total = int(payload.get("total", len(products)))
        except (TypeError, ValueError):
            total = len(products)
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = str(product.get("id") or "").strip()
            name = " ".join(str(product.get("name") or "").split())
            try:
                price = Decimal(str(product.get("price")))
            except (InvalidOperation, TypeError):
                continue
            if not product_id or not name or price <= 0:
                continue
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": " ".join(str(product.get("categoryName") or "general merchandise").split())[:500],
                "price": format(price, "f"),
                "currency": "SLE",
                "country": "Sierra Leone",
                "sector": "consumer_goods",
                "available": bool(product.get("isAvailable", True)) and int(product.get("stock") or 0) > 0,
                "url": f"https://saloneemarket.com/products/{product_id}",
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
        offset = int(response.meta.get("offset", 0))
        next_offset = offset + len(products)
        if products and next_offset < total and next_offset < 10_000:
            yield scrapy.Request(
                f"{API_URL}?limit=100&offset={next_offset}",
                callback=self.parse,
                meta={"offset": next_offset},
            )
