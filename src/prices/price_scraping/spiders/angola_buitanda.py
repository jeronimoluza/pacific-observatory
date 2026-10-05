"""Scrape Buitanda Angola's public paginated product API."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


API_URL = "https://api-production.buitanda.com/api/products"


def clean(value):
    return " ".join(str(value or "").split())


def parse_payload(response):
    try:
        payload = json.loads(response.text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [], 0
    body = payload.get("data") if isinstance(payload, dict) else None
    products = body.get("data") if isinstance(body, dict) else None
    meta = body.get("meta") if isinstance(body, dict) else None
    if not isinstance(products, list):
        return [], 0
    total = meta.get("total", len(products)) if isinstance(meta, dict) else len(products)
    try:
        total = int(total)
    except (TypeError, ValueError):
        total = len(products)
    return products, total


class AngolaBuitandaSpider(scrapy.Spider):
    name = "angola_buitanda"
    allowed_domains = ["api-production.buitanda.com", "www.buitanda.com"]
    start_urls = [f"{API_URL}?offset=0&limit=100"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://www.buitanda.com/",
        },
    }

    def parse(self, response):
        products, total = parse_payload(response)
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            if not isinstance(product, dict):
                continue
            product_id = clean(product.get("id"))
            name = clean(product.get("name"))
            slug = clean(product.get("slug") or product.get("SEOUrl") or product_id)
            categories = product.get("productCategories") or []
            category = clean(categories[0].get("name")) if categories and isinstance(categories[0], dict) else "general merchandise"
            variants = product.get("ProductVariant") or []
            if not product_id or not name or not isinstance(variants, list):
                continue
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                variant_id = clean(variant.get("id"))
                try:
                    price = Decimal(str(variant.get("finalPrice")))
                except (InvalidOperation, TypeError):
                    continue
                if not variant_id or price <= 0:
                    continue
                attributes = variant.get("attributes") or []
                labels = []
                for attribute in attributes:
                    if isinstance(attribute, dict):
                        value = clean(attribute.get("value") or attribute.get("name"))
                        if value:
                            labels.append(value)
                variant_name = f"{name} - {' / '.join(labels)}" if labels else name
                yield {
                    "product_id": f"{product_id}:{variant_id}",
                    "product_name": variant_name[:500],
                    "category": category[:500],
                    "price": format(price, "f"),
                    "currency": "AOA",
                    "country": "Angola",
                    "sector": "consumer_goods",
                    "available": int(variant.get("quantity") or 0) > 0,
                    "url": f"https://www.buitanda.com/product/{slug}",
                    "language": "pt",
                    "scraped_at_utc": scraped_at,
                }

        offset = int(response.meta.get("offset", 0))
        next_offset = offset + len(products)
        if products and next_offset < total and next_offset < 10_000:
            yield scrapy.Request(
                f"{API_URL}?offset={next_offset}&limit=100",
                callback=self.parse,
                meta={"offset": next_offset},
            )
