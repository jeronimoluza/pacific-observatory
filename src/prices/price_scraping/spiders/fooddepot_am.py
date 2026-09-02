"""fooddepot.am — Food Depot (Armenia), Bagisto storefront with an open JSON API.

The workbook flagged this ``SUSPECT`` ("category pages did not expose
prices in the fetch") because the storefront is a bare create-react-app
shell (``/`` returns ~11KB of HTML, no server-rendered product content).
But the JS bundle (``/static/js/main.*.chunk.js``) references
``https://api.fooddepot.am`` — a wide-open, unauthenticated Bagisto REST
API that this spider hits directly, plain HTTP, no Playwright needed
("Playwright to discover, plain HTTP to scrape").

Verified live 2026-09-01:
- ``GET /api/products/?limit=100&page=N`` — clean, SELF-TERMINATING
  pagination (``meta.last_page``), 2841 products across 29 pages. No
  wraparound trap (unlike sas_am/supermarket_am/parma_am).
- ``GET /api/categories`` — a small nested tree (5 roots: special
  offers/food-and-beverages/alcohol/equipment/household-goods) that has
  to be flattened recursively to map a product's ``cats`` id(s) to a leaf
  name; most products carry 0 or 1 category id.
- Names are Armenian by default (``name`` field, e.g. "Բնական Հյութ
  \"Andros\" Մուլտիմրգային 1լ") — no locale param needed.
- ``price`` is a decimal STRING already in whole AMD (e.g. "14500.0000"
  means 14,500 AMD, not 1.45 or 145.00) — do NOT treat the ".0000" as a
  meaningful subunit.
- PDP url is reconstructed as ``https://fooddepot.am/<url_key>`` (verified
  200; the SPA client-side-routes it, but it's a stable canonical link).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://api.fooddepot.am/api"
_PAGE_SIZE = 100


class FooddepotAmSpider(scrapy.Spider):
    name = "fooddepot_am"
    allowed_domains = ["api.fooddepot.am", "fooddepot.am"]
    currency = "AMD"
    language = "hy"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API_BASE}/categories",
            callback=self.parse_categories,
        )

    def parse_categories(self, response):
        cat_map: dict[int, str] = {}
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            data = {"categories": []}

        def _walk(nodes):
            for node in nodes:
                cat_map[node["id"]] = node.get("name") or None
                _walk(node.get("children") or [])

        _walk(data.get("categories") or [])
        logger.info("fooddepot_am: %d categories flattened", len(cat_map))

        yield scrapy.Request(
            f"{_API_BASE}/products/?limit={_PAGE_SIZE}&page=1",
            callback=self.parse_products,
            meta={"page": 1, "cat_map": cat_map},
        )

    def parse_products(self, response):
        page = response.meta["page"]
        cat_map = response.meta["cat_map"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning("fooddepot_am: page=%s not valid JSON", page)
            return

        rows = data.get("data") or []
        meta = data.get("meta") or {}
        last_page = meta.get("last_page", page)

        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for row in rows:
            item = self._parse_row(row, cat_map, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        logger.info(
            "fooddepot_am: page=%s/%s rows=%d items=%d",
            page,
            last_page,
            len(rows),
            emitted,
        )

        if page < last_page:
            yield scrapy.Request(
                f"{_API_BASE}/products/?limit={_PAGE_SIZE}&page={page + 1}",
                callback=self.parse_products,
                meta={"page": page + 1, "cat_map": cat_map},
            )

    def _parse_row(self, row, cat_map, scraped_at: str) -> dict | None:
        product_id = row.get("id")
        name = row.get("name")
        price_raw = row.get("price")
        url_key = row.get("url_key")

        if product_id is None or not name or price_raw is None or not url_key:
            return None

        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None

        cats = row.get("cats") or []
        category = cat_map.get(cats[0]) if cats else None

        name = re.sub(r"\s+", " ", name).strip()

        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": bool(row.get("in_stock", True)),
            "url": f"https://fooddepot.am/{url_key}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
