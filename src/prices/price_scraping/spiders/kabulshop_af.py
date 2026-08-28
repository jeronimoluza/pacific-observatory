"""
Spider for kabulshop.com -- Afghanistan online marketplace ("Kabul Shop").
Native-app-first (has iOS/Android app links); the web frontend is a thin
Angular SPA whose server always returns the same index.html shell for any
path, so no route in the shell itself can be trusted as a real PDP URL.

Backend is a same-brand API subdomain (`api.kabulshop.com`, "Badrang" —
product images are hosted at badrang.s3.ap-southeast-1.amazonaws.com). No
robots.txt exists on either host (that path also just re-serves the SPA
shell, HTTP 200 text/html).

Catalog endpoint: `GET https://api.kabulshop.com/productservice/products`.
This is NOT the homepage carousel the original probe found (which only
returns small curated sections: 24 "trending" + 24 "recentlyAdded" + 1 each
for a few tag rails). Confirmed live 2026-08-17: the `products` endpoint
returns the full flat catalog -- 477 distinct product ids -- in a single
call, and its (non-functional) `page`/`size` query params are ignored: page
0, page 1, and no-params-at-all all return the identical 477-id set. That
rules out "curated, unpaginated, worthless" -- this is the whole enumerable
catalog, not a homepage rail, just served in one shot rather than paged.

Prices are in AFN (Afghani; the API's own `currency` field is the Dari
string "افغانی", the Afghani's name, not an ISO code). A handful of rows
carry `price: 0` (unpriced "contact us" placeholders) -- these are skipped.
One extreme outlier was observed live (a skincare cream at ~795M AFN,
clearly a data-entry error) and is intentionally NOT filtered here per
this repo's convention of leaving unit-value outlier gating to the enrich
layer, not the spider.

The PDP URL below (`/product/<id>`) is a best-effort SPA route guess, not
independently verified (every path 200s identically off the same SPA
shell) -- `product_id` is the reliable identity key for this source.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://api.kabulshop.com/productservice/products"
_BASE = "https://kabulshop.com"


class KabulshopAfSpider(scrapy.Spider):
    name = "kabulshop_af"
    allowed_domains = ["kabulshop.com"]
    currency = "AFN"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_API, callback=self.parse_products)

    def parse_products(self, response):
        try:
            rows = response.json()
        except ValueError:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for row in rows:
            if row.get("isActive") is False:
                continue
            product_id = row.get("id")
            name = row.get("name")
            price = row.get("price")
            if not (product_id and name and price):
                continue
            category = " > ".join(row.get("category") or []) or None
            n += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(row.get("isAvailable", True)),
                "url": f"{_BASE}/product/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {n} rows from {len(rows)} raw catalog entries")
