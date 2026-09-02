"""
Spider for BiteLiqour -- a single, named, first-party bottle/liquor store in
Maseru, Lesotho, whose storefront is hosted on the LocalBites food-delivery
platform (store.localbites.co.ls/stores/biteliqour) rather than its own
domain. Same "merchant on an aggregator" pattern as the *_wolt_* and
*_lezzoo_* single-venue sources -- this spider walks ONLY this one
merchant's catalog, not LocalBites' cross-merchant marketplace (that is the
separate localbites_ls source, channel=marketplace, which deliberately
excludes this store to avoid double-collecting it).

BiteLiqour sells retail-size bottled alcohol and soft drinks/juices
(750ml whiskey, 1-2L soft drinks, 1L juice) -- a genuine beverage retailer,
not a restaurant -- hence channel=specialty-food.

REAL PAGINATED JSON API (fixed 2026-09-01, orchestrator-flagged page-1 cap):
the store page's server-rendered __NEXT_DATA__ blob is capped at page 1
(this was the spider's first cut, and it shipped only 24 of 66 rows -- a
flat capped count, the failure signature the shared brief warns about).
The frontend bundle (`/_next/static/chunks/*.js`) reveals the CLIENT-SIDE
fetch actually used to page through a store's catalog: `getProducts()`
calls `GET https://api.localbites.co.ls/api/delivery-zone/products` with
query params `store=<slug>`, `page`, `per_page`, `latitude`, `longitude`
(lat/long are REQUIRED -- omitting them returns HTTP 422
"The latitude field is required"; Maseru's coordinates are used as a
constant since the platform only needs *a* point inside its delivery
zone). Critically, this endpoint also requires `Accept: application/json`
-- without it, the host falls back to serving the SPA's HTML shell (200,
465KB, no JSON) instead of erroring, which is why this endpoint was easy to
miss on a first pass. Confirmed by walking page=1..5 with per_page=15: 66
distinct product ids across all 5 pages (`last_page` was accurate),
0 overlap between pages. Max per_page is 100 (per_page=200 -> 422 "must
not be greater than 100"), so a single page=1,per_page=100 request already
returns the full 66-item catalog; this spider still follows `last_page`
rather than assuming per_page=100 always covers everything, so it keeps
working if the catalog grows past 100 items.
"""

import json
import logging

from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://api.localbites.co.ls/api/delivery-zone/products"
_STORE_SLUG = "biteliqour"
_PER_PAGE = 100
# A point inside LocalBites' Maseru delivery zone; required by the API but
# does not affect which products are returned for a given `store` slug.
_LATITUDE = -29.3142
_LONGITUDE = 27.4833


def _page_url(page: int) -> str:
    params = {
        "store": _STORE_SLUG,
        "page": page,
        "per_page": _PER_PAGE,
        "latitude": _LATITUDE,
        "longitude": _LONGITUDE,
    }
    return f"{_API_BASE}?{urlencode(params)}"


class BiteLiqourLsSpider(scrapy.Spider):
    name = "bite_liqour_ls"
    allowed_domains = ["api.localbites.co.ls", "store.localbites.co.ls"]
    currency = "LSL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _page_url(1),
            headers={"Accept": "application/json"},
            callback=self.parse_page,
            errback=self.errback,
            cb_kwargs={"page": 1},
        )

    def parse_page(self, response, page):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(
                f"{self.name}: page {page} did not parse as JSON ({response.url})"
            )
            return
        d = payload.get("data", {})
        products = d.get("data", [])
        last_page = d.get("last_page", page)
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for p in products:
            title = p.get("title")
            slug = p.get("slug")
            price = p.get("special_price") or p.get("price")
            if not title or price in (None, 0) or not slug:
                continue
            n += 1
            yield {
                "product_id": str(p.get("id")),
                "product_name": str(title).strip()[:500],
                "category": p.get("category_name"),
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("availability", True)),
                "url": f"https://store.localbites.co.ls/products/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {n} items from page {page}/{last_page} "
            f"(total={d.get('total')})"
        )
        if page < last_page:
            yield scrapy.Request(
                _page_url(page + 1),
                headers={"Accept": "application/json"},
                callback=self.parse_page,
                errback=self.errback,
                cb_kwargs={"page": page + 1},
            )

    def errback(self, failure):
        logger.error(
            f"{self.name}: request failed {failure.request.url} — {failure.value!r}"
        )
