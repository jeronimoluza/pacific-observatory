"""
Spider for Chemist Warehouse (Australia) - https://www.chemistwarehouse.com.au

Next.js storefront whose product listing is served by a public Algolia index.
The search-only credentials (app id + api key + index) are embedded in the
site JS. We POST directly to the Algolia query endpoint - no Playwright, no
Akamai (the WAF only fronts the HTML pages, not the Algolia CDN).

Algolia caps a single query's paging window at 1000 hits, so the full ~36k
catalogue is traversed by recursively bisecting the calculatedPrice range into
disjoint bands until each band returns <=1000 hits, then paging that band.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_ID = "42NP1V2I98"
_API_KEY = "3ce54af79eae81a18144a7aa7ee10ec2"
_INDEX = "prod_cwr-cw-au_products_en"
_ENDPOINT = f"https://{_APP_ID}-dsn.algolia.net/1/indexes/{_INDEX}/query"

_HITS_PER_PAGE = 100
_WINDOW = 1000
_PRICE_MAX = 500000  # cents; catalogue max observed ~449900

_ATTRS = [
    "name",
    "calculatedPrice",
    "sku",
    "objectID",
    "slug",
    "categories",
    "productType",
    "isInStock",
]


class ChemistWarehouseSpider(scrapy.Spider):
    name = "chemist_warehouse"
    allowed_domains = ["algolia.net"]
    currency = "AUD"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }

    def _headers(self):
        return {
            "X-Algolia-Application-Id": _APP_ID,
            "X-Algolia-API-Key": _API_KEY,
            "Content-Type": "application/json",
        }

    def _query(self, lo, hi, page):
        body = {
            "query": "",
            "hitsPerPage": _HITS_PER_PAGE,
            "page": page,
            "numericFilters": [
                f"calculatedPrice>={lo}",
                f"calculatedPrice<{hi}",
            ],
            "attributesToRetrieve": _ATTRS,
        }
        return scrapy.Request(
            _ENDPOINT,
            method="POST",
            headers=self._headers(),
            body=json.dumps(body),
            callback=self.parse,
            meta={"lo": lo, "hi": hi, "page": page},
            dont_filter=True,
        )

    async def start(self):
        yield self._query(0, _PRICE_MAX, 0)

    def parse(self, response):
        lo = response.meta["lo"]
        hi = response.meta["hi"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.error("chemist_warehouse: non-JSON response for band %s-%s", lo, hi)
            return

        nb_hits = payload.get("nbHits", 0)

        if page == 0 and nb_hits > _WINDOW and (hi - lo) > 1:
            mid = (lo + hi) // 2
            logger.info(
                "chemist_warehouse: band %s-%s has %s hits, splitting at %s",
                lo,
                hi,
                nb_hits,
                mid,
            )
            yield self._query(lo, mid, 0)
            yield self._query(mid, hi, 0)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in payload.get("hits", []):
            item = self._build(hit, scraped_at)
            if item:
                yield item

        if page == 0:
            last = min((nb_hits - 1) // _HITS_PER_PAGE, _WINDOW // _HITS_PER_PAGE - 1)
            for p in range(1, last + 1):
                yield self._query(lo, hi, p)

    def _build(self, hit, scraped_at):
        cents = hit.get("calculatedPrice")
        if not cents or cents <= 0:
            return None
        if hit.get("isInStock") is False:
            return None
        name = (hit.get("name") or {}).get("en")
        if not name:
            return None
        slug = (hit.get("slug") or {}).get("en")
        url = f"https://www.chemistwarehouse.com.au/buy/{slug}" if slug else None
        return {
            "product_id": str(hit.get("sku") or hit.get("objectID")),
            "product_name": name[:500],
            "price": f"{cents / 100:.2f}",
            "currency": self.currency,
            "category": self._category(hit),
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def _category(self, hit):
        cats = (hit.get("categories") or {}).get("en") or {}
        deepest = None
        for lvl in ("lvl4", "lvl3", "lvl2", "lvl1", "lvl0"):
            vals = cats.get(lvl)
            if vals:
                deepest = vals[0]
                break
        if not deepest:
            return hit.get("productType") or None
        parts = [p.strip() for p in deepest.split(">")]
        parts = [
            p
            for p in parts
            if p and p not in ("Chemist Warehouse Australia", "Categories")
        ]
        return " > ".join(parts) if parts else (hit.get("productType") or None)
