"""Spider for VARUS (Ukraine) -- https://varus.ua/.

VARUS -- major Ukrainian supermarket/hypermarket chain (Dnipro-based,
60+ stores nationwide). The storefront is a client-hydrated Nuxt/Vue
Storefront SPA with no server-rendered product markup (the reason earlier
passes wrote this off as "SPA_HYDRATION, no lever isolated" -- see
known_blockers.md line 8383, "real open API, category parameterization not
yet isolated").

New approach 2026-09-11: a Playwright network trace of a live category click
found the real backend -- a Vue-Storefront-style Elasticsearch proxy at
``varus.ua/api/catalog/vue_storefront_catalog_2/product_v2/_search``. It is
wide open: no auth, no cookies, works from a cold ``curl_cffi`` session with
only ``Origin``/``Referer`` headers set (no impersonation profile required
beyond a normal browser UA). Verified live:

- ``category_ids`` filter (``eq``) selects any category id; using the root
  category (id=2, "Головна"/Home) returns the *entire* live catalog, so no
  category-tree walk is needed -- one query, paginated, covers everything
  reachable.
- The top-level ``price`` field on each hit is frequently 0 -- that is a
  stale/global list price, NOT the real quote. The real, region-scoped price
  lives at ``sqpp_data_region_default.price`` and is only populated
  correctly when the query also filters
  ``sqpp_data_region_default.in_stock: {"eq": true}``. Without that filter,
  ~65% of sampled rows carried a bogus 0 price; with it, 30/30 and 30/30
  sampled rows across two categories carried real non-zero UAH prices.
- Pagination is ``from``/``size`` against a plain Elasticsearch index and
  disjoint across pages (verified 0 id overlap, from=0 vs from=20). The
  index enforces the standard ES ``max_result_window`` -- ``from`` >= 10000
  hard-500s (verified: from=9980 OK, from=10000 fails). This caps a single
  category query at 10,000 rows; querying the root category is still by far
  the highest-yield single query, so the spider pages 0..9,900 (step 100)
  against category_id=2 rather than attempting a category-tree walk.
- PDP permalink is ``https://varus.ua/<url_key>`` (verified 200, full
  rendered page, matches the hit's ``url_key``/``url_path`` field).

No Playwright at collection time -- this is a pure ``scrapy_api`` spider.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://varus.ua"
_SEARCH_PATH = "/api/catalog/vue_storefront_catalog_2/product_v2/_search"
_ROOT_CATEGORY_ID = 2  # "Головна" -- the whole live catalog
_PAGE_SIZE = 100
_MAX_FROM = 9900  # ES max_result_window is 10000; last full page starts at 9900
_SHOP_ID = 3


def _search_url(frm: int) -> str:
    req = {
        "_availableFilters": [],
        "_appliedFilters": [
            {
                "attribute": "category_ids",
                "value": {"eq": _ROOT_CATEGORY_ID},
                "scope": "default",
            },
            {"attribute": "visibility", "value": {"in": [2, 4]}, "scope": "default"},
            {"attribute": "status", "value": {"in": [1]}, "scope": "default"},
            {
                "attribute": "sqpp_data_region_default.in_stock",
                "value": {"eq": True},
                "scope": "default",
            },
        ],
        "_appliedSort": [],
        "_searchText": "",
    }
    params = {
        "request": json.dumps(req, separators=(",", ":")),
        "request_format": "search-query",
        "response_format": "compact",
        "shop_id": _SHOP_ID,
        "size": _PAGE_SIZE,
        "from": frm,
        "sort": "",
    }
    return f"{_BASE}{_SEARCH_PATH}?{urlencode(params)}"


class VarusUaSpider(scrapy.Spider):
    name = "varus_ua"
    allowed_domains = ["varus.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Origin": "https://varus.ua",
            "Referer": "https://varus.ua/",
        },
    }

    async def start(self):
        for frm in range(0, _MAX_FROM + 1, _PAGE_SIZE):
            yield scrapy.Request(
                _search_url(frm),
                callback=self.parse_page,
                meta={"impersonate": "chrome124", "from": frm},
            )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning("varus_ua: non-JSON response at from=%s", response.meta.get("from"))
            return

        hits = data.get("hits") or []
        if not hits:
            return

        for h in hits:
            region = h.get("sqpp_data_region_default") or {}
            price = region.get("price")
            if not price or price <= 0:
                continue
            url_key = h.get("url_key") or h.get("url_path")
            if not url_key:
                continue
            name = (h.get("name") or "").strip()
            if not name:
                continue
            cats = h.get("category") or []
            category = cats[-1]["name"] if cats else None
            product_id = h.get("sku") or h.get("id")

            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": bool(region.get("in_stock", True)),
                "url": f"{_BASE}/{url_key}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
