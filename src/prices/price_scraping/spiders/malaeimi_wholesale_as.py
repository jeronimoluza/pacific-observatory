"""Spider for Malaeimi Wholesale - https://malaeimiwholesale.com/.

The Angular storefront shells product cards from a public API hosted at
https://malaeimi-api.fly.dev/api. This spider scopes to the site's food,
grocery and beverage category ids.
"""

from __future__ import annotations

from datetime import datetime, timezone

import scrapy

_API_BASE = "https://malaeimi-api.fly.dev/api"
_SITE_BASE = "https://malaeimiwholesale.com"
_CATEGORY_IDS = (6, 8, 9)  # Beverage, Food, Grocery
_PAGE_SIZE = 100


class MalaeimiWholesaleAsSpider(scrapy.Spider):
    name = "malaeimi_wholesale_as"
    allowed_domains = ["malaeimi-api.fly.dev", "malaeimiwholesale.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for category_id in _CATEGORY_IDS:
            yield scrapy.Request(
                self._url(category_id, page=0),
                callback=self.parse_page,
                meta={"category_id": category_id, "page": 0},
            )

    def parse_page(self, response):
        payload = response.json()
        rows = payload.get("content") if isinstance(payload, dict) else []
        scraped_at = datetime.now(timezone.utc).isoformat()

        for row in rows or []:
            item = self._item(row, scraped_at)
            if item:
                yield item

        page = int(response.meta["page"])
        total_pages = int(payload.get("totalPages") or 0)
        if page + 1 < total_pages:
            category_id = response.meta["category_id"]
            yield scrapy.Request(
                self._url(category_id, page=page + 1),
                callback=self.parse_page,
                meta={"category_id": category_id, "page": page + 1},
            )

    def _item(self, row: dict, scraped_at: str) -> dict | None:
        name = str(row.get("name") or "").strip()
        price = row.get("price")
        product_id = row.get("id")
        if not name or price in (None, "") or product_id in (None, ""):
            return None

        category = row.get("category") or {}
        subcategories = row.get("subcategories") or []
        parts = [category.get("name")] + [
            sub.get("name") for sub in subcategories if isinstance(sub, dict)
        ]
        category_label = " > ".join(part for part in parts if part)
        inventory = row.get("inventory")
        try:
            available = float(inventory or 0) > 0
        except (TypeError, ValueError):
            available = True

        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category_label or None,
            "price": str(price),
            "currency": self.currency,
            "available": available,
            "url": (
                f"{_SITE_BASE}/items?categoryId={category.get('id') or ''}"
                f"#item-{product_id}"
            ),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _url(category_id: int, page: int) -> str:
        return (
            f"{_API_BASE}/items?page={page}&size={_PAGE_SIZE}"
            f"&sort=name,asc&categoryId={category_id}"
        )
