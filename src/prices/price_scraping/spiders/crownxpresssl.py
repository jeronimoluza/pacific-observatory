"""Scrape Crown Xpress Freetown's public menu API."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


class CrownXpressSLSpider(scrapy.Spider):
    name = "crownxpresssl"
    allowed_domains = ["crownxpresssl.com"]
    start_urls = ["https://crownxpresssl.com/api/get_menu.php"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://crownxpresssl.com/menu/",
        },
    }

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        categories = payload.get("categories") if isinstance(payload, dict) else None
        if not isinstance(categories, list):
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_name = " ".join(str(category.get("name") or "menu").split())
            for item in category.get("items") or []:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "").strip()
                name = " ".join(str(item.get("name") or "").split())
                try:
                    price = Decimal(str(item.get("price")))
                except (InvalidOperation, TypeError):
                    continue
                if not item_id or not name or price <= 0:
                    continue
                yield {
                    "product_id": item_id,
                    "product_name": name[:500],
                    "category": category_name[:500],
                    "price": format(price, "f"),
                    "currency": "SLE",
                    "country": "Sierra Leone",
                    "sector": "food_service",
                    "available": bool(item.get("available", True)),
                    "url": f"https://crownxpresssl.com/menu/#item-{item_id}",
                    "language": "en",
                    "scraped_at_utc": scraped_at,
                }
