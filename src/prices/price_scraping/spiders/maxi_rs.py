"""
Spider for Maxi (Serbia) -- https://www.maxi.rs/.

Delhaize-group national leader (SAP Commerce Cloud / Hybris + Next.js +
Apollo GraphQL storefront). GOTCHA per the source list: Maxi's own FAQ
states online promotions MAY DIFFER from in-store -- record the channel
as `supermarket` but treat this as the online-channel price series.

Fingerprinting gotcha: Akamai Bot Manager (`sec-if-cpt-container`
behavioral challenge page, "Powered and protected by Akamai") intercepts
category-page requests under `impersonate="chrome124"`/`"chrome120"`
inconsistently -- `impersonate="firefox133"` cleared it 6/6 tries live
2026-09-06 and is what this spider uses.

A Playwright network trace (2026-09-06) of a category page found the
storefront calls a GraphQL persisted-query endpoint directly as a GET:
`GET /api/v1/?operationName=GetCategoryProductSearch&variables=...
&extensions={"persistedQuery":{"version":1,"sha256Hash":"d8bff391..."}}`.
Hitting this directly needs only one extra header
(`apollo-require-preflight: true`) to dodge an Apollo Server CSRF guard
-- no cookies or session needed. `pageSize` is capped (100 -> 500
BAD_USER_INPUT; 20, the value the real page uses, works). Response
carries `pagination.totalPages` for clean termination and each product's
full `price` object (`value`, `currencyIso`, `wasPrice`) plus
`firstLevelCategory.name`. Verified live: category 02 "Mlecni proizvodi i
jaja" (dairy/eggs), 470 products / 24 pages; "Mleko sterilizovano Maxi
2,8%mm 1l" RSD 99.99.

16 top-level category codes are SSR'd in the homepage's own nav
(`/<slug>/c/<code>`) and are hardcoded here rather than re-discovered
per run, since Maxi's top-level taxonomy is stable.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.maxi.rs"
_API_URL = f"{_BASE}/api/v1/"
_PERSISTED_HASH = "d8bff3916275ffeb6f51604d36d7a3aa2f9cd92847487a7f2e3bdf6bb2115cdd"
_PAGE_SIZE = 20
MAX_PAGES_PER_CATEGORY = 10

# Top-level category codes, SSR'd in the homepage nav (confirmed live 2026-09-06).
_CATEGORY_CODES = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "20",
]


class MaxiRsSpider(scrapy.Spider):
    name = "maxi_rs"
    allowed_domains = ["maxi.rs"]
    currency = "RSD"
    language = "sr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        # Akamai's behavioral challenge (sec-if-cpt-container) intercepted
        # chrome124/chrome120 impersonation inconsistently; firefox133
        # cleared it 6/6 tries live 2026-09-06. Pins the project-wide
        # RandomBrowserMiddleware pool to firefox133 for this spider only.
        "IMPERSONATE_BROWSERS": ["firefox133"],
    }

    def _request(self, category: str, page: int):
        import urllib.parse as up

        variables = {
            "lang": "sr",
            "searchQuery": ":relevance",
            "sort": "relevance",
            "category": category,
            "pageNumber": page,
            "pageSize": _PAGE_SIZE,
            "filterFlag": True,
            "fields": "PRODUCT_TILE",
            "plainChildCategories": True,
        }
        extensions = {"persistedQuery": {"version": 1, "sha256Hash": _PERSISTED_HASH}}
        query = up.urlencode(
            {
                "operationName": "GetCategoryProductSearch",
                "variables": json.dumps(variables, separators=(",", ":")),
                "extensions": json.dumps(extensions, separators=(",", ":")),
            }
        )
        url = f"{_API_URL}?{query}"
        return scrapy.Request(
            url,
            headers={"apollo-require-preflight": "true"},
            callback=self.parse_page,
            meta={"category": category, "page": page},
        )

    async def start(self):
        for code in _CATEGORY_CODES:
            req = self._request(code, 0)
            yield req

    def parse_page(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning("maxi_rs: bad JSON for category %s page %s", category, page)
            return
        data = (payload.get("data") or {}).get("categoryProductSearch")
        if not data:
            logger.warning(
                "maxi_rs: no data for category %s page %s: %s",
                category,
                page,
                payload.get("errors"),
            )
            return
        for product in data.get("products") or []:
            item = self._item(product)
            if item:
                yield item

        pagination = data.get("pagination") or {}
        total_pages = pagination.get("totalPages", 0)
        if page + 1 < total_pages and page + 1 < MAX_PAGES_PER_CATEGORY:
            yield self._request(category, page + 1)

    def _item(self, p: dict):
        name = (p.get("name") or "").strip()
        code = str(p.get("code") or "")
        price_obj = p.get("price") or {}
        price = price_obj.get("value")
        if not name or not code or price in (None, "", 0):
            return None
        category_name = (p.get("firstLevelCategory") or {}).get("name")
        return {
            "product_id": code,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": category_name,
            "price": str(price),
            "currency": price_obj.get("currencyIso") or self.currency,
            "available": bool(p.get("available", True)),
            "url": f"{_BASE}/p/{code}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
