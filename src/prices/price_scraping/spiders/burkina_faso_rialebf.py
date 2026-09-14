"""Scrape RialeBF's public paginated marketplace API."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


API_URL = "https://rialebf.com/api/products"
PAGE_SIZE = 24
MAX_PRODUCTS = 10_000
NON_CONSUMER_RE = re.compile(
    r"\b(?:service|formation|coaching|location|immobilier|terrain|parcelle|"
    r"appartement|maison|emploi|vehicule|voiture|moto)\b",
    re.IGNORECASE,
)


def parse_products(payload, scraped_at=None):
    """Yield positive-price tangible products from an API payload."""
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return
    scraped_at = scraped_at or datetime.now(timezone.utc).isoformat()
    seen = set()
    for product in payload["items"]:
        if not isinstance(product, dict):
            continue
        product_id = str(product.get("id") or "").strip()
        name = " ".join(str(product.get("title") or "").split())
        category = " ".join(str(product.get("category") or "marketplace").split())
        if (
            not product_id
            or not name
            or product_id in seen
            or NON_CONSUMER_RE.search(f"{name} {category}")
        ):
            continue
        raw_price = (
            product.get("discountedPrice")
            if product.get("hasDiscount") and product.get("discountedPrice") is not None
            else product.get("price")
        )
        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, TypeError):
            continue
        if price <= 0:
            continue
        try:
            available = int(product.get("stock") or 0) > 0
        except (TypeError, ValueError):
            available = False
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category[:500],
            "price": format(price, "f"),
            "currency": "XOF",
            "country": "Burkina Faso",
            "sector": "consumer_goods",
            "available": available,
            "url": f"https://rialebf.com/product/{product_id}",
            "language": "fr",
            "scraped_at_utc": scraped_at,
        }


class BurkinaFasoRialeBFSpider(scrapy.Spider):
    name = "burkina_faso_rialebf"
    allowed_domains = ["rialebf.com"]
    start_urls = [
        f"{API_URL}?page=1&limit={PAGE_SIZE}&search=&sortBy=relevance"
    ]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://rialebf.com/marketplace",
        },
    }

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        yield from parse_products(payload)

        try:
            page = int(payload.get("page", 1))
            limit = int(payload.get("limit", PAGE_SIZE))
            total = min(int(payload.get("total", 0)), MAX_PRODUCTS)
        except (AttributeError, TypeError, ValueError):
            return
        if limit > 0 and page * limit < total:
            next_page = page + 1
            yield scrapy.Request(
                f"{API_URL}?page={next_page}&limit={PAGE_SIZE}&search=&sortBy=relevance",
                callback=self.parse,
            )
