"""
Sainsbury's (UK) — https://www.sainsburys.co.uk/.

Public, unauthenticated JSON search API backs the online grocery catalogue:

    GET /groceries-api/gol-services/product/v1/product
        ?filter[keyword]=<term>&page_number=<n>

Probed 2026-08-31 with curl_cffi impersonate="chrome124": 200 OK, no auth,
no Referer/X-Requested-With required. `filter[keyword]=` (empty) returns
the site's own default/most-popular ranking across the whole catalogue —
`controls.total_record_count` reports 10000 but the walk actually dead-ends
at HTTP 400 on page 166 (60/page => 165 usable pages, ~9,900 distinct
products). Verified page-to-page: walking `page_number` 1..15 for
`filter[keyword]=milk` returned exactly `total_record_count` (885) distinct
`product_uid`s with zero repeats — the cursor is a real page number, not an
offset.

`full_url` in the payload is protocol-relative ("://www.sainsburys.co.uk/
gol-ui/product/..."); prepend "https:". `retail_price.price` is the
per-unit shelf price already in GBP (site is GBP-only, no currency field
in the payload — confirmed against countries.yaml).
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.sainsburys.co.uk"
API_URL = f"{BASE_URL}/groceries-api/gol-services/product/v1/product"


def _normalize_url(full_url):
    """`full_url` in the payload is inconsistently shaped across requests:
    observed both a bare-colon protocol-relative form ("://host/path") and
    a fully-qualified form ("https://host/path"). Handle both rather than
    assuming one, or a blind prefix produces "httpshttps://...".
    """
    if not full_url:
        return None
    if full_url.startswith("http://") or full_url.startswith("https://"):
        return full_url
    if full_url.startswith("://"):
        return f"https{full_url}"
    if full_url.startswith("//"):
        return f"https:{full_url}"
    return urljoin(BASE_URL, full_url)


class SainsburysUkSpider(scrapy.Spider):
    name = "sainsburys_uk"
    allowed_domains = ["sainsburys.co.uk"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page_number):
        return scrapy.Request(
            f"{API_URL}?filter[keyword]=&page_number={page_number}",
            callback=self.parse,
            errback=self.errback,
            meta={"page_number": page_number},
            dont_filter=True,
        )

    def parse(self, response):
        page_number = response.meta["page_number"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON at page {page_number}")
            return

        products = data.get("products") or []
        for product in products:
            name = (product.get("name") or "").strip()
            uid = product.get("product_uid") or ""
            retail_price = (product.get("retail_price") or {}).get("price")
            url = _normalize_url(product.get("full_url"))
            if not name or uid == "" or retail_price is None or not url:
                continue
            categories = product.get("categories") or []
            category = categories[0].get("name") if categories else None
            yield {
                "product_id": str(uid),
                "product_name": name[:500],
                "category": category,
                "price": str(retail_price),
                "currency": self.currency,
                "available": bool(product.get("is_available", True)),
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: page={page_number} got={len(products)} "
            f"total={data.get('controls', {}).get('total_record_count')}"
        )

        # The server's own total_record_count/last are unreliable (report
        # 10000/167 but the walk 400s at page 166) — stop on a non-200 or an
        # empty page rather than trusting the advertised last page.
        if response.status == 200 and products:
            yield self._page_request(page_number + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
