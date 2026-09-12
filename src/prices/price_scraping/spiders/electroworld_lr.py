"""Electro World Inc. -- https://electroworldinc.online/

Monrovia electronics and appliance retailer (Randall Street, Monrovia --
confirmed from the store's own /api/public-config). Phones, TVs, laptops,
audio, cameras, kitchen appliances, furniture.

Probed live 2026-09-12. The HTML is a 4.8 KB Vite SPA shell -- every route,
including PDPs listed in its own sitemap, returns the same empty shell with
zero prices, which is why the earlier triage read it as "landing shell only".
The bundle at /assets/index-*.js names the backend, and it is completely open
and unauthenticated:

    GET /api/products        -> JSON array, the ENTIRE catalog in one call
                                (242 products measured 2026-09-12, all with
                                 integer prices, all active=1, none null)
    GET /api/products?limit= -> paginated envelope {products,total,limit,
                                offset,hasMore} -- not needed, the bare call
                                returns everything
    GET /api/public-config   -> {"store_name":"Electro World Inc.",
                                 "currency":"USD",
                                 "store_address":"Randall Street . Monrovia ,
                                 Liberia", ...}

That is the "Playwright to discover, plain HTTP to scrape" pattern: nothing
renders at collection time.

CURRENCY: USD, and for once not a judgement call -- the store's own
/api/public-config states currency USD explicitly. Recorded because Liberia is
a dual-currency USD/LRD economy.

Page family parsed: API (/api/products). The emitted url is the human
permalink /<category>/<slug>, which matches the site's sitemap shape but is
never fetched by this spider (and would return the SPA shell if it were).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import scrapy

_BASE = "https://electroworldinc.online"


class ElectroworldLrSpider(scrapy.Spider):
    name = "electroworld_lr"
    allowed_domains = ["electroworldinc.online"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    async def start(self):
        yield scrapy.Request(f"{_BASE}/api/products", callback=self.parse_api)

    def parse_api(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning(f"{self.name}: non-JSON at {response.url}")
            return
        rows = payload if isinstance(payload, list) else payload.get("products", [])
        self.logger.info(f"{self.name}: {len(rows)} products from /api/products")
        for row in rows:
            if not row.get("active", 1):
                continue
            price = row.get("price")
            name = (row.get("name") or "").strip()
            if not name or price in (None, ""):
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            cat = row.get("category")
            slug = row.get("slug")
            url = f"{_BASE}/{cat}/{slug}" if cat and slug else _BASE
            yield {
                "product_id": row.get("id"),
                "product_name": name[:500],
                "price": str(price),
                "currency": self.currency,
                "category": row.get("subcategory") or cat,
                "url": url,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
