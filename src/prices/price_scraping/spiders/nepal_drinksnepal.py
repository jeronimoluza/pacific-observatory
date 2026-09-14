"""Scrape the complete public Drinks Nepal WooCommerce catalogue."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


API_URL = "https://shop.drinksnepal.com/wp-json/wc/store/v1/products?per_page=100&page={}"


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
        product_id = clean(product.get("id"))
        name = clean(product.get("name"))
        url = clean(product.get("permalink"))
        if not product_id or not name or not url or prices.get("currency_code") != "NPR":
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
            "currency": "NPR",
            "country": "Nepal",
            "sector": "consumer_goods",
            "available": bool(product.get("is_in_stock")),
            "url": url,
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class NepalDrinksnepalSpider(scrapy.Spider):
    name = "nepal_drinksnepal"
    allowed_domains = ["shop.drinksnepal.com"]
    start_urls = [API_URL.format(1)]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://drinksnepal.com/",
        },
    }

    def parse(self, response):
        yield from parse_products(response)
        page = int(response.meta.get("page", 1))
        try:
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
        except (TypeError, ValueError):
            total_pages = 1
        if page < total_pages:
            next_page = page + 1
            yield scrapy.Request(API_URL.format(next_page), callback=self.parse, meta={"page": next_page})
