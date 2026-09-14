"""Scrape product records embedded by Smart ConneXXionZ Suriname."""
from __future__ import annotations

import json
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
                slug = str(product.get("slug") or "").strip()
                name = " ".join(str(product.get("name") or "").split())
                if not product_id or not slug or not name or product_id in seen:
                    continue
                try:
                    price = Decimal(str(product.get("price")))
                except (InvalidOperation, TypeError):
                    continue
                if price <= 0:
                    continue
                seen.add(product_id)
                yield {
                    "product_id": product_id,
                    "product_name": name[:500],
                    "category": None,
                    "price": format(price, "f"),
                    "currency": "SRD",
                    "country": "Suriname",
                    "sector": "consumer_goods",
                    "available": True,
                    "url": response.urljoin(f"/products/{slug}"),
                    "language": "nl",
                    "scraped_at_utc": scraped_at,
                }


class SurinameSmartconnexxionzSpider(scrapy.Spider):
    name = "suriname_smartconnexxionz"
    allowed_domains = ["smart-dev.zeus1.tad.sr"]
    start_urls = ["https://smart-dev.zeus1.tad.sr/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
