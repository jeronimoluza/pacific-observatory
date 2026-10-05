"""Scrape Penchami Marketplace's public Gambia product API."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def clean(value):
    return " ".join(str(value or "").split())


def parse_products(response):
    try:
        products = json.loads(response.text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(products, list):
        return

    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for product in products:
        if not isinstance(product, dict):
            continue
        product_id = clean(product.get("id"))
        name = clean(product.get("name"))
        if (
            not product_id
            or not name
            or product_id in seen
            or not product.get("isActive")
            or product.get("approvalStatus") != "approved"
        ):
            continue
        try:
            price = Decimal(str(product.get("price")))
        except (InvalidOperation, TypeError):
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        vendor = clean((product.get("vendor") or {}).get("storeName"))
        category = clean((product.get("category") or {}).get("name"))
        if vendor:
            name += f" - {vendor}"
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": (category or "general merchandise")[:500],
            "price": format(price, "f"),
            "currency": "GMD",
            "country": "Gambia",
            "sector": "consumer_goods",
            "available": int(product.get("stock") or 0) > 0,
            "url": response.urljoin(f"/products/{product_id}"),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class GambiaPenchamiSpider(scrapy.Spider):
    name = "gambia_penchami"
    allowed_domains = ["penchami.com", "www.penchami.com"]
    start_urls = ["https://www.penchami.com/api/products"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://www.penchami.com/products",
        },
    }

    def parse(self, response):
        yield from parse_products(response)
