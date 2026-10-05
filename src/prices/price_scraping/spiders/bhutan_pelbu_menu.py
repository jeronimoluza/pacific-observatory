"""Scrape the current structured menu from Pelbu Suites Bhutan."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


SLUG_RE = re.compile(r"[^a-z0-9]+")


def parse_menu(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for raw in response.css('script[type="application/ld+json"]::text').getall():
        try:
            records = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(records, list):
            records = [records]
        for record in records:
            if record.get("@type") != "Menu":
                continue
            sections = record.get("hasMenuSection") or []
            if isinstance(sections, dict):
                sections = [sections]
            for section in sections:
                for item in section.get("hasMenuItem") or []:
                    offer = item.get("offers") or {}
                    name = " ".join(str(item.get("name") or "").split())
                    if offer.get("priceCurrency") != "BTN" or not name:
                        continue
                    try:
                        price = Decimal(str(offer.get("price")))
                    except (InvalidOperation, TypeError):
                        continue
                    product_id = SLUG_RE.sub("-", name.lower()).strip("-")
                    if price <= 0 or not product_id or product_id in seen:
                        continue
                    seen.add(product_id)
                    yield {
                        "product_id": product_id,
                        "product_name": name[:500],
                        "category": section.get("name") or "Current menu",
                        "price": format(price, "f"),
                        "currency": "BTN",
                        "country": "Bhutan",
                        "sector": "consumer_goods",
                        "available": True,
                        "url": f"{response.url}#{product_id}",
                        "language": "en",
                        "scraped_at_utc": scraped_at,
                    }


class BhutanPelbuMenuSpider(scrapy.Spider):
    name = "bhutan_pelbu_menu"
    allowed_domains = ["pelbusuites.bt", "www.pelbusuites.bt"]
    start_urls = ["https://www.pelbusuites.bt/menu"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_menu(response)
