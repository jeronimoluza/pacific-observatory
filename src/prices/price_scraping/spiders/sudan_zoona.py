"""Scrape Zoona Sudan's public first-party product API."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_products(response):
    try:
        payload = json.loads(response.text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, list):
        return

    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for product in payload:
        if not isinstance(product, dict):
            continue
        product_id = str(product.get("id") or "").strip()
        name = " ".join(str(product.get("name") or "").split())
        if not product_id or not name or product_id in seen:
            continue
        try:
            price = Decimal(str(product.get("price")))
        except (InvalidOperation, TypeError):
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        category = " ".join(str(product.get("category") or "general merchandise").split())
        supplied_url = str(product.get("url") or "").strip()
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category[:500],
            "price": format(price, "f"),
            "currency": "SDG",
            "country": "Sudan",
            "sector": "consumer_goods",
            "available": not bool(product.get("is_out_of_stock")),
            "url": supplied_url or f"{response.url}#product-{product_id}",
            "language": "ar",
            "scraped_at_utc": scraped_at,
        }


class SudanZoonaSpider(scrapy.Spider):
    name = "sudan_zoona"
    allowed_domains = ["zoonasd.com"]
    start_urls = ["https://zoonasd.com/api/products"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://zoonasd.com/",
        },
    }

    def parse(self, response):
        yield from parse_products(response)
