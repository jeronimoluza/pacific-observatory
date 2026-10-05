"""Scrape current category records embedded by Chynabazar Nepal."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

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
                name = " ".join(str(product.get("title") or "").split())
                sku = str(product.get("sku") or "").strip()
                if not product_id or not slug or not name or product_id in seen:
                    continue
                try:
                    price = Decimal(str(product.get("numericPrice")))
                except (InvalidOperation, TypeError):
                    continue
                if price <= 0:
                    continue
                seen.add(product_id)
                suffix = f"?{urlencode({'sku': sku})}" if sku else ""
                yield {
                    "product_id": product_id,
                    "product_name": name[:500],
                    "category": "stationery",
                    "price": format(price, "f"),
                    "currency": "NPR",
                    "country": "Nepal",
                    "sector": "consumer_goods",
                    "available": product.get("stockStatus") == "in_stock",
                    "url": response.urljoin(f"/product/{slug}{suffix}"),
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }


def pagination(response):
    for payload in _next_payloads(response):
        match = re.search(
            r'"totalResults":(\d+),"currentPage":(\d+),"perPage":(\d+)',
            payload,
        )
        if match:
            return tuple(map(int, match.groups()))
    return None


class NepalChynabazarSpider(scrapy.Spider):
    name = "nepal_chynabazar"
    allowed_domains = ["chynabazar.com"]
    start_urls = ["https://chynabazar.com/categories/stationery"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
        page_state = pagination(response)
        if page_state:
            total, current, per_page = page_state
            if current * per_page < total:
                yield response.follow(
                    f"{self.start_urls[0]}?page={current + 1}",
                    callback=self.parse,
                )
