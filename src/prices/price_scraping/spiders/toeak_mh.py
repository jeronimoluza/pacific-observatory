"""Toeak Bar & Grill Majuro menu prices embedded in Wix JSON."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import scrapy


_STATE_RE = re.compile(r'<script[^>]*id="wix-warmup-data"[^>]*>(.*?)</script>', re.S)
_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class ToeakMhSpider(scrapy.Spider):
    name = "toeak_mh"
    allowed_domains = ["toeak.com", "www.toeak.com"]
    start_urls = ["https://www.toeak.com/menus?menu=toeak-bar--grill"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for section in response.css('[data-hook="section.container"]'):
            category = _clean(section.css('[data-hook="section.name"]::text').get())
            category = category or "Restaurant menu item"
            for item in section.css('[data-hook="item.container"]'):
                name = _clean(item.css('[data-hook="item.name"]::text').get())
                price_text = _clean(item.css('[data-hook="item.price"]::text').get())
                price_match = _PRICE_RE.search(price_text)
                if not name or not price_match:
                    continue
                product_id = _slug(f"{category}-{name}")
                if product_id in seen:
                    continue
                seen.add(product_id)
                description = _clean(
                    " ".join(item.css('[data-hook="item.description"]::text').getall())
                )
                yield {
                    "product_id": product_id,
                    "product_name": f"Toeak Bar & Grill {name}"[:500],
                    "category": category,
                    "price": price_match.group(1),
                    "price_text": price_text,
                    "currency": self.currency,
                    "available": True,
                    "unit": "menu item",
                    "description": description or None,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

        if seen:
            return

        warmup = self._warmup_json(response.text)
        for section in self._walk_dicts(warmup):
            items = section.get("items")
            if not isinstance(items, list):
                continue
            category = _clean(section.get("name")) or "Restaurant menu item"
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = _clean(item.get("name"))
                price_info = item.get("priceInfo") or {}
                price = _clean(price_info.get("price"))
                if not name or not price:
                    continue
                try:
                    float(price)
                except ValueError:
                    continue

                item_id = _clean(item.get("id")) or _slug(name)
                if item_id in seen:
                    continue
                seen.add(item_id)
                description = _clean(item.get("description"))
                yield {
                    "product_id": item_id,
                    "product_name": f"Toeak Bar & Grill {name}"[:500],
                    "category": category,
                    "price": price,
                    "currency": self.currency,
                    "available": bool(item.get("visible", True)),
                    "unit": "menu item",
                    "description": description or None,
                    "url": f"{response.url}#{_slug(name)}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

    @staticmethod
    def _warmup_json(text: str) -> object:
        match = _STATE_RE.search(text)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    def _walk_dicts(self, value: object):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from self._walk_dicts(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._walk_dicts(child)
