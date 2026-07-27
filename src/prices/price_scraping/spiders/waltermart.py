"""
Spider for WalterMart Delivery (Philippines) - waltermartdelivery.com.ph.

Uses the NCR Freshop catalog API directly (api.freshop.ncrcloud.com) with the
public app_key `walter_mart` - no auth required. Bypasses the storefront SPA.

The /2/products endpoint hard-caps a response at 100 rows and IGNORES offset /
page / token pagination (offset=0 and offset=5000 return the identical slice),
so the catalogue cannot be walked by paging. Instead we shard on leaf
department_id: the /1/departments taxonomy is a parent/child tree, and each leaf
department is narrow enough to fit under the 100-row cap for most nodes.
Departments that still exceed the cap are logged as a coverage gap rather than
silently truncated. Items belong to several departments, so the collect run's
DuplicationPipeline (url_hash) folds the overlap.

Category text is derived from each item's canonical_url path (the numeric
`category` field is an opaque code, not useful for downstream classification).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_APP_KEY = "walter_mart"
_BASE = "https://api.freshop.ncrcloud.com"
_DEPARTMENTS = _BASE + "/1/departments"
_PRODUCTS = _BASE + "/2/products"
# /2/products returns at most 100 rows and ignores offset/page/token, so this is
# a hard ceiling per department shard, not a page size we can advance past.
_PAGE_CAP = 100


class WaltermartSpider(scrapy.Spider):
    name = "waltermart"
    allowed_domains = ["api.freshop.ncrcloud.com"]
    currency = "PHP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        # The curl_cffi impersonate handler raises SSLError against this Freshop
        # host (and the same requests 502 through it); a plain Twisted client
        # negotiates TLS cleanly. Disable RandomBrowserMiddleware so requests
        # skip curl_cffi and route through the standard handler. The API 403s a
        # non-browser UA, so keep CustomUserAgentMiddleware in place.
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.8,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield scrapy.Request(
            f"{_DEPARTMENTS}?app_key={_APP_KEY}&limit=2000",
            callback=self.parse_departments,
            headers={"Accept": "application/json"},
        )

    def parse_departments(self, response):
        try:
            depts = json.loads(response.text).get("items") or []
        except json.JSONDecodeError:
            logger.error("waltermart: non-JSON departments response")
            return
        parent_ids = {d.get("parent_id") for d in depts if d.get("parent_id")}
        leaves = [d["id"] for d in depts if d.get("id") and d["id"] not in parent_ids]
        logger.info(
            "waltermart: %d departments, %d leaf shards", len(depts), len(leaves)
        )
        for did in leaves:
            yield self._department_request(did)

    def _department_request(self, department_id):
        return scrapy.Request(
            f"{_PRODUCTS}?app_key={_APP_KEY}&limit={_PAGE_CAP}"
            f"&sort=id&department_id={department_id}",
            callback=self.parse_page,
            meta={"department_id": department_id},
            headers={"Accept": "application/json"},
        )

    @staticmethod
    def _category_from_url(canonical_url):
        if not canonical_url:
            return None
        m = re.search(r"/shop_by_category/(.+?)/p/", canonical_url)
        if not m:
            return None
        parts = [p.replace("_", " ").strip() for p in m.group(1).split("/") if p]
        return " > ".join(parts) if parts else None

    def parse_page(self, response):
        department_id = response.meta["department_id"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(
                "waltermart: non-JSON response for department %s", department_id
            )
            return

        items = payload.get("items") or []
        total = payload.get("total") or 0
        if total > _PAGE_CAP:
            logger.warning(
                "waltermart: department=%s total=%d exceeds cap %d — %d rows missed",
                department_id,
                total,
                _PAGE_CAP,
                total - _PAGE_CAP,
            )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            name = it.get("name")
            price = it.get("unit_price")
            if not name or price is None:
                continue
            yield {
                "product_id": it.get("upc") or str(it.get("id", "")),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": self._category_from_url(it.get("canonical_url")),
                "url": it.get("canonical_url"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    def errback(self, failure):
        logger.error(
            "waltermart: request failed %s — %r", failure.request.url, failure.value
        )
