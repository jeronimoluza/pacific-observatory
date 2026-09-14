"""Scrape ZmaDookan's public paginated grocery product API."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


API_URL = "https://zmadookan.com/api/v1/products"
NON_TANGIBLE_RE = re.compile(
    r"\b(?:delivery|gift card|membership|service|subscription)\b",
    re.IGNORECASE,
)


def clean(value) -> str:
    return " ".join(str(value or "").split())


def parse_payload(response):
    try:
        payload = json.loads(response.text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return [], {}
    products = payload.get("data") if isinstance(payload, dict) else None
    pagination = payload.get("pagination") if isinstance(payload, dict) else None
    if not isinstance(products, list):
        return [], {}
    return products, pagination if isinstance(pagination, dict) else {}


def product_to_item(product, scraped_at):
    if not isinstance(product, dict):
        return None
    product_id = clean(product.get("id"))
    name = clean(product.get("name"))
    if (
        not product_id
        or not name
        or NON_TANGIBLE_RE.search(name)
        or product.get("is_active") in (0, False, "0")
    ):
        return None
    try:
        price = Decimal(str(product.get("price")))
        stock = int(product.get("stock") or 0)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if price <= 0:
        return None
    return {
        "product_id": product_id,
        "product_name": name[:500],
        "category": f"grocery:{clean(product.get('category_id')) or 'uncategorized'}",
        "price": format(price, "f"),
        "currency": "AFN",
        "country": "Afghanistan",
        "sector": "consumer_goods",
        "available": stock > 0,
        "url": f"https://zmadookan.com/product/{product_id}",
        "language": "en",
        "scraped_at_utc": scraped_at,
    }


class AfghanistanZmaDookanSpider(scrapy.Spider):
    name = "afghanistan_zmadookan"
    allowed_domains = ["zmadookan.com"]
    start_urls = [f"{API_URL}?page=1&limit=40"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://zmadookan.com/shop",
        },
    }

    def parse(self, response):
        products, pagination = parse_payload(response)
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            item = product_to_item(product, scraped_at)
            if item:
                yield item

        try:
            page = int(pagination.get("page", response.meta.get("page", 1)))
            total_pages = int(pagination.get("totalPages", page))
        except (TypeError, ValueError):
            return
        if products and page < total_pages and page < 250:
            next_page = page + 1
            yield scrapy.Request(
                f"{API_URL}?page={next_page}&limit=40",
                callback=self.parse,
                meta={"page": next_page},
            )
