"""MYK Suppliers Solomon Islands cleaning and household supplies."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

_PRICE_RE = re.compile(r"^\d[\d,]*(?:\.\d{1,2})?$")
_SKIP = {
    "refurbish photocopy machine out right payment",
    "refurbish photocopy machine leasing",
    "solar pv cleaning",
    "water purification systems service",
}


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(text.replace("\xa0", " ").split())


class MykSuppliersSbSpider(scrapy.Spider):
    name = "myk_suppliers_sb"
    allowed_domains = ["myk-suppliers.com", "www.myk-suppliers.com"]
    start_urls = ["https://www.myk-suppliers.com/store"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        context = self._store_context(response)
        if not context:
            return

        seen: set[str] = set()
        for item in context.get("items", []):
            name = _clean(item.get("title"))
            if not self._candidate_name(name):
                continue
            price_info = item.get("price") or {}
            price = _clean(price_info.get("value")).replace(",", "")
            if not _PRICE_RE.match(price) or float(price) <= 0:
                continue
            url = urljoin(response.url, item.get("fullUrl") or "")
            if not url:
                continue
            key = f"{url}|{price}"
            if key in seen:
                continue
            seen.add(key)
            product_id = self._product_id(item, name, price)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Cleaning and household supplies",
                "price": price,
                "currency": _clean(price_info.get("currency")) or self.currency,
                "available": not bool(item.get("soldOut")),
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        next_page = (context.get("pagination") or {}).get("nextPageUrl")
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    @staticmethod
    def _store_context(response) -> dict:
        raw = response.css(".product-list::attr(data-context)").get()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _candidate_name(text: str) -> str | None:
        candidate = _clean(text).strip(" -:;")
        lowered = candidate.lower()
        if not candidate or lowered in _SKIP:
            return None
        if lowered.startswith(("image", "$", "quick view", "price ranges")):
            return None
        if any(marker in lowered for marker in (" lease", " leasing", " service", "payment")):
            return None
        if _PRICE_RE.match(candidate) or re.fullmatch(r"[\d\s./-]+", candidate):
            return None
        if len(candidate) > 120:
            return None
        return candidate

    @staticmethod
    def _product_id(item: dict, name: str, price: str) -> str:
        variant = item.get("firstInStockVariant") or {}
        variant_id = _clean(variant.get("id"))
        if variant_id:
            return variant_id
        item_id = _clean(item.get("id"))
        if item_id:
            return item_id
        return hashlib.sha1(f"{name}|{price}".encode("utf-8")).hexdigest()[:16]
