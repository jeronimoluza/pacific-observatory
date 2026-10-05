"""Scrape tangible consumer listings embedded by Yougou Guinea."""
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
    decoder = json.JSONDecoder()
    products = {}
    for payload in _next_payloads(response):
        start = 0
        marker = '{"_id":'
        while True:
            start = payload.find(marker, start)
            if start < 0:
                break
            try:
                product, consumed = decoder.raw_decode(payload[start:])
            except json.JSONDecodeError:
                start += 1
                continue
            start += consumed
            if isinstance(product, dict) and product.get("title") and product.get("price"):
                products[str(product.get("_id"))] = product

    scraped_at = datetime.now(timezone.utc).isoformat()
    for product_id, product in products.items():
        if not product.get("active") or product.get("category") == "Services & Emploi":
            continue
        name = " ".join(str(product.get("title") or "").split())
        seller = " ".join(str(product.get("sellerName") or "").split())
        try:
            price = Decimal(str(product.get("price")))
        except (InvalidOperation, TypeError):
            continue
        if not name or price <= 0:
            continue
        if seller:
            name += f" - {seller}"
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": product.get("subCategory") or product.get("category"),
            "price": format(price, "f"),
            "currency": "GNF",
            "country": "Guinea",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(f"/annonces/{product_id}"),
            "language": "fr",
            "scraped_at_utc": scraped_at,
        }


class GuineaYougouSpider(scrapy.Spider):
    name = "guinea_yougou"
    allowed_domains = ["yougouyougou.net", "www.yougouyougou.net"]
    start_urls = ["https://yougouyougou.net/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
