"""nhonest_rw — N.Honest Supermarket (Kigali, Rwanda), open JSON API.

The storefront (honestsupermarket.com) is a jQuery/Bootstrap single-page
site: products are injected into a `#products-section` anchor on the
homepage via `fetch()` calls to a same-origin API (`js/script.js`). No
Playwright needed — the API is wide open, no auth, plain HTTP:

- ``GET /api/products?page=N&limit=L`` — paginates the full catalogue
  (``totalPages``/``totalCount`` in the response). Verified live
  2026-09-01: 5,206 products across 29 categories (groceries, fresh food,
  beverages, personal care, household, clothing, stationery, etc.) —
  channel: supermarket.
- ``GET /api/categories`` — 29 top-level categories with names and counts.
- ``GET /api/settings/public`` — confirms store currency RWF.

The site has no per-product detail page/route (single-page catalogue, no
PDP URLs in the JS bundle) — DuplicationPipeline dedups on ``item['url']``,
so each row is given a synthetic ``#product-<id>`` fragment on the site
root per onboarding rule 9, rather than reusing one bare homepage URL for
every row.

Prices are plain RWF integers in the API (e.g. ``13000``) — RWF has no
minor unit, so no decimal precision is fabricated.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://www.honestsupermarket.com/api"
_SITE_ROOT = "https://www.honestsupermarket.com/"
_PAGE_SIZE = 100


class NhonestRwSpider(scrapy.Spider):
    name = "nhonest_rw"
    allowed_domains = ["www.honestsupermarket.com", "honestsupermarket.com"]
    currency = "RWF"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        headers = {
            "Accept": "application/json",
            "Origin": "https://www.honestsupermarket.com",
            "Referer": "https://www.honestsupermarket.com/",
        }
        yield scrapy.Request(
            f"{_API_BASE}/products?page=1&limit={_PAGE_SIZE}",
            headers=headers,
            callback=self.parse_products,
            meta={"page": 1, "headers": headers},
        )

    def parse_products(self, response):
        page = response.meta["page"]
        headers = response.meta["headers"]
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning("nhonest_rw: page=%s not valid JSON", page)
            return

        rows = data.get("products") or []
        total_pages = data.get("totalPages", page)

        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for row in rows:
            item = self._parse_row(row, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        logger.info(
            "nhonest_rw: page=%s/%s rows=%d items=%d",
            page,
            total_pages,
            len(rows),
            emitted,
        )

        if page < total_pages:
            yield scrapy.Request(
                f"{_API_BASE}/products?page={page + 1}&limit={_PAGE_SIZE}",
                headers=headers,
                callback=self.parse_products,
                meta={"page": page + 1, "headers": headers},
            )

    def _parse_row(self, row, scraped_at: str) -> dict | None:
        product_id = row.get("_id")
        name = row.get("name")
        price_raw = row.get("price")

        if not product_id or not name or price_raw is None:
            return None

        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None

        category = (row.get("category") or {}).get("name")
        name = re.sub(r"\s+", " ", name).strip()

        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": not bool(row.get("notAvailable", False)),
            "url": f"{_SITE_ROOT}#product-{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
