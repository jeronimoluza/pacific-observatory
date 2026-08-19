"""Spider for Vhandar (Nepal) — https://www.vhandar.com/.

Next.js frontend backed by a separate API host, api.vhandar.com. Plain curl,
no auth. Re-verified live 2026-08-06:
GET https://api.vhandar.com/products?status=active&page=1&limit=100 -> 200,
JSON `{"data": {"data": [...], "pagination": {"total": 1180, ...}}}`.
Sample: 'Sip & Seal Matcha Powder' unit=g unitValue=100 pricePerUnit=1600.
Paginate by incrementing `page` until `pagination.isLastPage` is true.

GET https://api.vhandar.com/categories returns top-level categories with
name + id; product objects only carry `categoryIds` (id references, no
names), so we fetch categories once at start and map the first categoryId to
a top-level category name where possible.

No explicit currency field on products; the storefront is Nepal-only and
prices are unambiguously NPR (matches countries.yaml).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_PRODUCTS_URL = "https://api.vhandar.com/products"
_CATEGORIES_URL = "https://api.vhandar.com/categories"
_LIMIT = 100
_MAX_PAGES = 50  # safety cap; 1180 products / 100 per page ~= 12 pages


class VhandarNpSpider(scrapy.Spider):
    name = "vhandar_np"
    allowed_domains = ["api.vhandar.com"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_CATEGORIES_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        cat_map = {}
        try:
            data = response.json()
            for c in data.get("data", {}).get("data", []):
                cid = c.get("_id")
                cname = c.get("name")
                if cid and cname:
                    cat_map[cid] = cname
        except ValueError:
            logger.warning("vhandar_np: categories response not valid JSON")
        yield scrapy.Request(
            f"{_PRODUCTS_URL}?status=active&page=1&limit={_LIMIT}",
            callback=self.parse_page,
            meta={"page": 1, "cat_map": cat_map},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"vhandar_np: non-JSON response at {response.url}")
            return
        data = payload.get("data", {})
        products = data.get("data") or []
        pagination = data.get("pagination") or {}
        page = response.meta["page"]
        cat_map = response.meta["cat_map"]
        logger.info(
            f"vhandar_np page={page} count={len(products)} total={pagination.get('total')}"
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, cat_map, scraped_at)
            if item:
                yield item
        if not pagination.get("isLastPage", True) and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_PRODUCTS_URL}?status=active&page={nxt}&limit={_LIMIT}",
                callback=self.parse_page,
                meta={"page": nxt, "cat_map": cat_map},
            )

    def _item(self, p: dict, cat_map: dict, scraped_at: str):
        price = p.get("pricePerUnit")
        if price is None:
            return None
        cat_ids = p.get("categoryIds") or []
        category = cat_map.get(cat_ids[0]) if cat_ids else None
        product_id = str(p.get("_id") or "")
        return {
            "product_id": product_id,
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://www.vhandar.com/#{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
