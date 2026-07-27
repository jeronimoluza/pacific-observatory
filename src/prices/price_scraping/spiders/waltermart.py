"""
Spider for WalterMart Delivery (Philippines) - waltermartdelivery.com.ph.

Uses the NCR Freshop catalog API directly (api.freshop.ncrcloud.com) with the
public app_key `walter_mart` - no auth required. Bypasses the storefront SPA.
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
_API = "https://api.freshop.ncrcloud.com/2/products"
# Freshop caps page size (~24); larger limits 502. Keep it small + gentle delay
# to avoid the host's TLS-layer IP throttle.
_PAGE_SIZE = 24


class WaltermartSpider(scrapy.Spider):
    name = "waltermart"
    allowed_domains = ["api.freshop.ncrcloud.com"]
    currency = "PHP"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 2,
        "RETRY_HTTP_CODES": [500, 503, 504, 408, 429],
    }

    async def start(self):
        yield self._page_request(offset=0)

    def _page_request(self, offset):
        url = f"{_API}?app_key={_APP_KEY}&limit={_PAGE_SIZE}&offset={offset}"
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"offset": offset},
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
        offset = response.meta["offset"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("waltermart: non-JSON response at offset %d", offset)
            return

        items = payload.get("items") or []
        total = payload.get("total") or 0
        logger.info(
            "waltermart: offset=%d items=%d total=%d", offset, len(items), total
        )
        if not items:
            return

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

        next_offset = offset + _PAGE_SIZE
        if next_offset < total:
            yield self._page_request(offset=next_offset)

    def errback(self, failure):
        logger.error(
            "waltermart: request failed %s — %r", failure.request.url, failure.value
        )
