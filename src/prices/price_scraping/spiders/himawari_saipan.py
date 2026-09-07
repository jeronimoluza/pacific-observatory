"""Himawari Saipan online menu -- server-rendered JSON-LD menu tree."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://www.himawarisaipan.com/menu"


class HimawariSaipanSpider(scrapy.Spider):
    name = "himawari_saipan"
    allowed_domains = ["himawarisaipan.com", "www.himawarisaipan.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 2.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse_menu)

    def parse_menu(self, response):
        scripts = response.css('script[type="application/ld+json"]::text').getall()
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for text in scripts:
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            menu = data.get("menu") if isinstance(data, dict) else None
            if not isinstance(menu, dict):
                continue
            for row in self._walk_menu(menu, scraped_at):
                emitted += 1
                yield row
        logger.info("himawari_saipan: emitted %d menu items", emitted)

    def _walk_menu(self, node: dict, scraped_at: str, category: str | None = None):
        category = node.get("name") or category
        for item in node.get("hasMenuItem") or []:
            row = self._item(item, category, scraped_at)
            if row:
                yield row
        for section in node.get("hasMenuSection") or []:
            if isinstance(section, dict):
                yield from self._walk_menu(section, scraped_at, category)

    def _item(self, item: dict, category: str | None, scraped_at: str):
        name = str(item.get("name") or "").strip()
        offer = item.get("offers") or {}
        price = offer.get("price")
        if not name or price is None:
            return None
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            return None
        if price_value <= 0:
            return None
        ident = f"{category or ''}|{name}|{price_value:.2f}"
        availability = str(offer.get("availability") or "").lower()
        product_id = hashlib.sha1(ident.encode("utf-8")).hexdigest()[:16]
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "price": f"{price_value:.2f}",
            "currency": offer.get("priceCurrency") or self.currency,
            "category": category,
            "available": "soldout" not in availability,
            "url": f"{_URL}?item={product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
