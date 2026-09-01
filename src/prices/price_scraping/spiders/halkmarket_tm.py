"""
Halk Market (Turkmenistan) — https://halkmarket.com.tm/.

Nuxt 3 SPA (empty server-rendered shell, no product markup in the initial
HTML). The bundled JS (`/_nuxt/HaWKaeHJ.js`) calls a same-origin JSON API:

    GET  /api/category                -> top-level + nested category tree
    POST /api/products/all            -> paginated product listing
         body: {"categories": [...], "brands": [], "shops": [],
                 "priceFrom": null, "priceTo": null, "ordering": "recommended",
                 "search": "", "page": N, "pageSize": 100,
                 "discount": false, "isLiked": false}

Neither endpoint needs auth or a Referer/X-Requested-With header. Walked by
top-level category id (23 categories) rather than the unfiltered listing so
each row can carry a real category label; per-category `count`/pageSize
determine the page count. Verified page=1 vs page=2 within one category
share zero product ids (real page advance, not a re-served window). Summed
per-category counts (1,854) closely match the unfiltered total (1,858) —
the handful of uncategorized items are skipped rather than double-counted.

Catalog is almost entirely food/beverage: dairy & eggs, frozen, drinks,
snacks, hot drinks, pasta/grains, sauces, baby food, bakery, meat, kitchen
staples, nuts/dried fruit, ready meals, fish/seafood, canned goods, fruit &
veg. The only non-food category buckets (beauty, home, cleaning, pet,
clothing) had 0 live listings at probe time (2026-08-31).

Prices are plain numeric TMT (e.g. 306.8 TMT/kg for Turkish figs, 29.8 TMT
for a 36g coffee sachet) with no explicit currency field on the row --
matches src/configs/countries.yaml (turkmenistan -> TMT) and the site has
no country/currency switcher.

There is no server-routable per-product URL (product detail opens in a
client-side modal on the SPA's /products route); the emitted `url` is
`https://halkmarket.com.tm/products?id=<id>`, unique per product for
DuplicationPipeline purposes and traceable back to the real product id.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://halkmarket.com.tm"
PAGE_SIZE = 100


class HalkmarketTmSpider(scrapy.Spider):
    name = "halkmarket_tm"
    allowed_domains = ["halkmarket.com.tm"]
    currency = "TMT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE_URL}/api/category",
            headers={"Accept": "application/json", "Accept-Language": "ru"},
            callback=self.parse_categories,
            errback=self.errback,
        )

    def parse_categories(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.error(f"{self.name}: non-JSON category response")
            return
        rows = data.get("data", {}).get("rows") or []
        logger.info(f"{self.name}: {len(rows)} top-level categories")
        for cat in rows:
            cid = cat.get("id")
            name = cat.get("name") or ""
            if not cid:
                continue
            yield self._api_request(cid, name, page=1)

    def _api_request(self, category_id, category_name, page):
        body = {
            "categories": [category_id],
            "brands": [],
            "shops": [],
            "priceFrom": None,
            "priceTo": None,
            "ordering": "recommended",
            "search": "",
            "page": page,
            "pageSize": PAGE_SIZE,
            "discount": False,
            "isLiked": False,
        }
        return scrapy.Request(
            f"{BASE_URL}/api/products/all",
            method="POST",
            body=json.dumps(body),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Language": "ru",
            },
            callback=self.parse_products,
            errback=self.errback,
            meta={
                "category_id": category_id,
                "category_name": category_name,
                "page": page,
            },
            dont_filter=True,
        )

    def parse_products(self, response):
        category_id = response.meta["category_id"]
        category_name = response.meta["category_name"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                f"{self.name}: non-JSON products response for {category_name}"
            )
            return
        data = payload.get("data") or {}
        rows = data.get("rows") or []
        count = data.get("count", 0)

        for row in rows:
            pid = row.get("id")
            name = (row.get("name") or "").strip()
            price = row.get("price")
            if not pid or not name or price is None:
                continue
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": category_name,
                "price": str(price),
                "currency": self.currency,
                "available": row.get("visibility") == "enabled",
                "url": f"{BASE_URL}/products?id={pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: category={category_name} page={page} got={len(rows)} count={count}"
        )

        if page * PAGE_SIZE < count:
            yield self._api_request(category_id, category_name, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
