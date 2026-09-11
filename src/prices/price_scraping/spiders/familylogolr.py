"""Spider for Family Logo Lr (Liberia) -- https://familylogolr.com/.

Bespoke Next.js (App Router / Turbopack) multi-vendor marketplace template --
not Shopify/Woo/Presta/OpenCart. The frontend calls a same-origin JSON API at
GET /api/products?limit=N&page=N (paginated, {success, data:{data:[...],
pagination:{...}}} envelope), discovered by probing the obvious /api/*
convention rather than by reading the JS bundle (the bundle is Turbopack-
chunked and does not name the endpoint in plain text).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://familylogolr.com"
API_URL = f"{BASE}/api/products"
PER_PAGE = 50
MAX_PAGES = 10


class FamilylogolrSpider(scrapy.Spider):
    name = "familylogolr"
    allowed_domains = ["familylogolr.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
    }

    async def start(self):
        yield scrapy.Request(
            f"{API_URL}?limit={PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"familylogolr: non-JSON response at {response.url}")
            return
        data = (payload or {}).get("data") or {}
        products = data.get("data") or []
        pagination = data.get("pagination") or {}
        page = response.meta["page"]
        logger.info(f"familylogolr: page={page} count={len(products)} pagination={pagination}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if pagination.get("hasNext") and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{API_URL}?limit={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict):
        price = p.get("salePrice") or p.get("price")
        if price is None:
            return None
        slug = p.get("slug") or p.get("handle") or p.get("_id")
        if not slug:
            return None
        return {
            "product_id": str(p.get("_id") or slug),
            "product_name": str(p.get("name") or p.get("title") or "").strip()[:500],
            "category": None,
            "price": str(price),
            "currency": p.get("currency") or self.currency,
            "available": True,
            "url": f"{BASE}/en/products/{slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
