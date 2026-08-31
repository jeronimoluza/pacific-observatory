"""
TM Pick n Pay (Zimbabwe) — https://tmpnponline.co.zw/.

Next.js (app router) storefront; product cards render client-side, so the
raw HTML shell carries no prices. The `app/layout` JS chunk hardcodes an
axios instance with baseURL "https://api.tmpnponline.co.zw" (a Laravel
API, X-Requested-With/XSRF headers set) and calls a standard Laravel
paginated endpoint:

    GET https://api.tmpnponline.co.zw/api/v1/products?page=<N>

`per_page` is accepted by the URL but ignored server-side (always 10 rows
regardless of the value sent) — page size is fixed. `last_page` in the
response body (measured 1072 pages / total=10719 products 2026-08-31) is
the walk bound; the spider follows it rather than counting rows, so an
API change to page size doesn't silently truncate the crawl. Each row
also carries a huge `stock_levels` array (per-branch stock across ~70 TM
Pick n Pay / Pick n Pay stores) that is not needed for a national price
observation and is ignored.

Product detail pages ARE server-rendered at /products/<slug> and contain
the name (verified), so that route is used as the canonical `url`.

Zimbabwe is dollarised; prices come back as plain "2.85" USD strings with
no currency field on the row, so USD is assumed (confirmed against the
site's default display currency).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://api.tmpnponline.co.zw"
SITE_BASE = "https://tmpnponline.co.zw"


class TmpnpZwSpider(scrapy.Spider):
    name = "tmpnp_zw"
    allowed_domains = ["tmpnponline.co.zw", "api.tmpnponline.co.zw"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _api_request(self, page):
        return scrapy.Request(
            f"{API_BASE}/api/v1/products?page={page}",
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "Referer": f"{SITE_BASE}/",
            },
            meta={"page": page},
            dont_filter=True,
        )

    async def start(self):
        yield self._api_request(1)

    def parse_api(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        rows = data.get("data") or []
        for row in rows:
            name = (row.get("name") or "").strip()
            price = row.get("sale_price") if row.get("on_sale") else row.get("price")
            slug = row.get("slug") or ""
            pid = row.get("id")
            if not name or price is None or pid is None:
                continue
            category = (row.get("product_category") or {}).get("name") or ""
            yield {
                "product_id": str(pid),
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": (row.get("status") == "published")
                and (row.get("stock_quantity") or 0) > 0,
                "url": f"{SITE_BASE}/products/{slug}"
                if slug
                else f"{SITE_BASE}/products/{pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        last_page = data.get("last_page") or page
        logger.info(
            f"{self.name}: page={page}/{last_page} got={len(rows)} total={data.get('total')}"
        )

        if rows and page < last_page:
            yield self._api_request(page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
