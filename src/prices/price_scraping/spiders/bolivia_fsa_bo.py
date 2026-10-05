"""Scrape current product cards from Farmacias Santa Ana Bolivia."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


class BoliviaFsaBoSpider(scrapy.Spider):
    name = "bolivia_fsa_bo"
    allowed_domains = ["fsa.bo", "www.fsa.bo"]
    start_urls = ["https://fsa.bo/"]

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for node in response.css("[idproducto][producto][precio]"):
            product_id = (node.attrib.get("idproducto") or "").strip()
            name = " ".join((node.attrib.get("producto") or "").split())
            raw_price = (node.attrib.get("precio") or "").strip()
            if not (product_id and name and raw_price) or product_id in seen:
                continue
            try:
                price = Decimal(raw_price)
            except InvalidOperation:
                continue
            if price <= 0:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": str(price),
                "currency": "BOB",
                "country": "Bolivia",
                "sector": "consumer_goods",
                "available": True,
                "url": response.urljoin(f"/producto/detalle/{product_id}"),
                "language": "es",
                "scraped_at_utc": scraped_at,
            }
