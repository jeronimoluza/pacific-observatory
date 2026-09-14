"""Scrape current grocery records embedded by Nubri Mart Nepal."""
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
        marker = '"product":'
        while True:
            start = payload.find(marker, start)
            if start < 0:
                break
            start += len(marker)
            try:
                product, consumed = decoder.raw_decode(payload[start:])
            except json.JSONDecodeError:
                continue
            start += consumed
            slug = str(product.get("slug") or "").strip()
            name = " ".join(str(product.get("nameEn") or "").split())
            if not slug or not name or slug in seen:
                continue
            try:
                price = Decimal(str(product.get("priceNpr")))
            except (InvalidOperation, TypeError):
                continue
            if price <= 0:
                continue
            seen.add(slug)
            yield {
                "product_id": product.get("merokiranaId") or slug,
                "product_name": name[:500],
                "category": product.get("categorySlug"),
                "price": format(price, "f"),
                "currency": "NPR",
                "country": "Nepal",
                "sector": "consumer_goods",
                "available": True,
                "url": response.urljoin(f"/product/{slug}/"),
                "language": "en",
                "scraped_at_utc": scraped_at,
            }


class NepalNubrimartSpider(scrapy.Spider):
    name = "nepal_nubrimart"
    allowed_domains = ["nubrimart.com", "www.nubrimart.com"]
    start_urls = ["https://www.nubrimart.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
