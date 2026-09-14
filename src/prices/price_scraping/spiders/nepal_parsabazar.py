"""Scrape current grocery records embedded by ParsaBazar Nepal."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def _next_payloads(response):
    marker = "self.__next_f.push([1,"
    decoder = json.JSONDecoder()
    for raw in response.css("script:not([src])::text").getall():
        start = 0
        while True:
            start = raw.find(marker, start)
            if start < 0:
                break
            start += len(marker)
            try:
                payload, consumed = decoder.raw_decode(raw[start:])
            except json.JSONDecodeError:
                break
            if isinstance(payload, str):
                yield payload
            start += consumed


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    decoder = json.JSONDecoder()
    seen = set()
    for payload in _next_payloads(response):
        start = 0
        marker = '"products":'
        while True:
            start = payload.find(marker, start)
            if start < 0:
                break
            start += len(marker)
            try:
                products, consumed = decoder.raw_decode(payload[start:])
            except json.JSONDecodeError:
                continue
            start += consumed
            if not isinstance(products, list):
                continue
            for product in products:
                product_id = str(product.get("id") or "").strip()
                name = " ".join(str(product.get("name") or "").split())
                if not product_id or not name or product_id in seen:
                    continue
                try:
                    price = Decimal(str(product.get("list_price")))
                except (InvalidOperation, TypeError):
                    continue
                if price <= 0:
                    continue
                seen.add(product_id)
                yield {
                    "product_id": product_id,
                    "product_name": name[:500],
                    "category": (
                        product.get("website_subcategory")
                        or product.get("website_category")
                    ),
                    "price": format(price, "f"),
                    "currency": "NPR",
                    "country": "Nepal",
                    "sector": "consumer_goods",
                    "available": Decimal(str(product.get("qty_available") or 0)) > 0,
                    "url": response.urljoin(
                        f"/products/{_slug(name)}-p{product_id}"
                    ),
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }


class NepalParsabazarSpider(scrapy.Spider):
    name = "nepal_parsabazar"
    allowed_domains = ["parsabazar.com", "www.parsabazar.com"]
    start_urls = ["https://parsabazar.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
