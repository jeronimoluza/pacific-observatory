"""
Shared base for dex.sy-hosted Syrian storefronts.

dex.sy is a Syrian single-vendor storefront host: each merchant gets
`<store>.dex.sy`, a Next.js App Router front end backed by a public,
unauthenticated JSON API at `/api/products`.

MEASURED 2026-09-12 (curl_cffi impersonate=chrome124, no auth, no
cookies, no Referer needed):

    GET https://<store>.dex.sy/api/products?page=N&limit=48
    -> {"success": true,
        "data": [{"productId", "name", "sku", "slug", "price",
                  "salePrice", "discount", "stockQuantity", "unit",
                  "brand", "category", "subCategory", ...}, ...],
        "meta": {"page", "limit", "total", "totalPages", "hasNext", ...}}

ENUMERABILITY (MEASURED, all three onboarded stores): page 1 vs page 2 at
limit=24 returned disjoint productId sets, zero overlap -- genuine
pagination, not a homepage carousel. Totals: nana 37, mid 49, karazzah 37.

CURRENCY: NOT in the API payload. Read instead from the storefront
homepage's own embedded store config (`"baseCurrency":"SYP"` inside the
Next.js RSC flight payload) -- confirmed SYP for all three stores on
2026-09-12, not inferred from the .sy TLD. Each subclass pins the value
it was measured with, so a store that later reprices in USD shows up as a
mismatch rather than silently mislabelled rows.

PRICE FIELDS: `price` is the list price and `salePrice` the effective
one; on every product sampled they were equal where no campaign ran.
We emit `salePrice` when it is a positive number lower than `price`,
else `price` -- i.e. the price a shopper actually pays.

Page family: API. The `url` emitted is the PDP permalink
(`https://<store>.dex.sy/products/<slug>`, verified 200) which this
spider never fetches.

Underscored filename -- Scrapy's SpiderLoader skips classes without `name`.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PER_PAGE = 48
MAX_PAGES = 60  # safety cap


class DexSyBaseSpider(scrapy.Spider):
    name = None
    STORE_HOST: str = ""
    currency = "SYP"
    language = "ar"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _page_url(self, page: int) -> str:
        return f"https://{self.STORE_HOST}/api/products?page={page}&limit={PER_PAGE}"

    async def start(self):
        yield scrapy.Request(
            self._page_url(1), callback=self.parse_page, meta={"page": 1}
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        products = payload.get("data") or []
        page = response.meta["page"]
        logger.info(f"{self.name} page={page} count={len(products)}")

        for p in products:
            item = self._item(p)
            if item:
                yield item

        meta = payload.get("meta") or {}
        if meta.get("hasNext") and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._page_url(nxt), callback=self.parse_page, meta={"page": nxt}
            )

    def _item(self, p: dict):
        price = p.get("price")
        sale = p.get("salePrice")
        try:
            value = float(price) if price is not None else None
        except (TypeError, ValueError):
            value = None
        try:
            sale_value = float(sale) if sale is not None else None
        except (TypeError, ValueError):
            sale_value = None
        if sale_value is not None and 0 < sale_value < (value or float("inf")):
            value = sale_value
        if value is None or value <= 0:
            return None

        name = str(p.get("name") or "").strip()
        if not name:
            return None

        cat = p.get("category")
        if isinstance(cat, dict):
            cat = cat.get("name")
        sub = p.get("subCategory")
        if isinstance(sub, dict):
            sub = sub.get("name")
        category = " > ".join(x for x in (cat, sub) if x) or None

        slug = p.get("slug")
        return {
            "product_id": str(p.get("sku") or p.get("productId")),
            "product_name": name[:500],
            "category": category,
            "price": str(value),
            "currency": self.currency,
            "available": bool((p.get("stockQuantity") or 0) > 0),
            "url": f"https://{self.STORE_HOST}/products/{slug}" if slug else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
