"""haha_rw — haha.rw (Kigali, Rwanda), open JSON API behind a React SPA.

haha.rw is a Vite/React SPA ("Online Groceries Platform") — the homepage
ships an empty ``<div id="root">`` and hydrates client-side. The JS bundle
(``/assets/index-*.js``) references a same-origin-adjacent API host
(``api.haha.rw``) that is wide open, no auth required:

- ``GET https://api.haha.rw/items?page=N&limit=L`` — the product catalogue,
  paginated (``data.pagination.totalItems``/``totalPages``). Verified live
  2026-09-01: 58 items total, single page.
- ``GET https://api.haha.rw/categories`` — 4 categories (Meat, Fruits,
  Vegetables and Legumes, Grain (Cereal)).
- ``GET https://api.haha.rw/local-markets`` — exactly one active market,
  "Nyabugogo Market" (Kigali) — a genuine physical fresh-produce/wholesale
  market, not a virtual aggregator. channel: fresh-market.

The React app exposes a client-side route ``/product/:productName/:id``
(seen in the bundle's router table) — used here to build a stable,
real per-product URL even though the route is client-rendered.

Prices are decimal strings in the API (e.g. ``"800.00"``) but RWF has no
minor unit — this is just the source's own formatting, not fabricated
precision; parsed straight with ``float()``.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://api.haha.rw"
_SITE_ROOT = "https://haha.rw"
_PAGE_SIZE = 100


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "item"


class HahaRwSpider(scrapy.Spider):
    name = "haha_rw"
    allowed_domains = ["api.haha.rw", "haha.rw"]
    currency = "RWF"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        headers = {
            "Accept": "application/json",
            "Origin": "https://haha.rw",
            "Referer": "https://haha.rw/",
        }
        yield scrapy.Request(
            f"{_API_BASE}/items?page=1&limit={_PAGE_SIZE}",
            headers=headers,
            callback=self.parse_items,
            meta={"page": 1, "headers": headers},
        )

    def parse_items(self, response):
        page = response.meta["page"]
        headers = response.meta["headers"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning("haha_rw: page=%s not valid JSON", page)
            return

        data = payload.get("data") or {}
        rows = data.get("items") or []
        pagination = data.get("pagination") or {}
        total_pages = pagination.get("totalPages", page)

        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for row in rows:
            item = self._parse_row(row, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        logger.info(
            "haha_rw: page=%s/%s rows=%d items=%d",
            page,
            total_pages,
            len(rows),
            emitted,
        )

        if page < total_pages:
            yield scrapy.Request(
                f"{_API_BASE}/items?page={page + 1}&limit={_PAGE_SIZE}",
                headers=headers,
                callback=self.parse_items,
                meta={"page": page + 1, "headers": headers},
            )

    def _parse_row(self, row, scraped_at: str) -> dict | None:
        product_id = row.get("id")
        name = row.get("name")
        price_raw = row.get("price")

        if product_id is None or not name or price_raw is None:
            return None

        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None

        category = (row.get("category") or {}).get("name")
        name_clean = re.sub(r"\s+", " ", name).strip()
        slug = quote(_slugify(name_clean))

        return {
            "product_id": str(product_id),
            "product_name": name_clean[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": bool(row.get("isPublic", True)),
            "url": f"{_SITE_ROOT}/product/{slug}/{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
