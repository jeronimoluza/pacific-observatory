"""Scrape Daarishop's public WooCommerce product catalogue for Chad."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


def clean(value):
    return " ".join(unescape(str(value or "")).split())


def parse_products(response):
    try:
        products = json.loads(response.text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(products, list):
        return

    scraped_at = datetime.now(timezone.utc).isoformat()
    for product in products:
        prices = product.get("prices") or {}
        product_id = str(product.get("id") or "").strip()
        name = clean(product.get("name"))
        url = str(product.get("permalink") or "").strip()
        if not product_id or not name or not url or prices.get("currency_code") != "EUR":
            continue
        try:
            minor_unit = int(prices.get("currency_minor_unit", 2))
            price = Decimal(str(prices.get("price"))) / (Decimal(10) ** minor_unit)
        except (InvalidOperation, TypeError, ValueError):
            continue
        if price <= 0:
            continue
        categories = product.get("categories") or []
        category = clean(categories[0].get("name")) if categories else "general merchandise"
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category[:500],
            "price": format(price, "f"),
            "currency": "EUR",
            "country": "Chad",
            "sector": "consumer_goods",
            "available": bool(product.get("is_in_stock")),
            "url": url,
            "language": "fr",
            "scraped_at_utc": scraped_at,
        }


class ChadDaarishopSpider(scrapy.Spider):
    name = "chad_daarishop"
    allowed_domains = ["daarishop.fr"]
    start_urls = ["https://daarishop.fr/wp-json/wc/store/v1/products?per_page=100&page=1"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://daarishop.fr/",
        },
    }

    def parse(self, response):
        yield from parse_products(response)
