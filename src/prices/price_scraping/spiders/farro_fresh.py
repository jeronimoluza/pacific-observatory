import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://www.farro.co.nz/api/ViewModel/Search/Search"
_PAGE_SIZE = 100


class FarroFreshSpider(scrapy.Spider):
    name = "farro_fresh"
    allowed_domains = ["farro.co.nz"]
    currency = "NZD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.farro.co.nz",
            "Referer": "https://www.farro.co.nz/shop/products/grocery",
        },
    }

    def _request(self, skip=0):
        body = {
            "searchPattern": "",
            "sortBy": "",
            "skip": skip,
            "take": _PAGE_SIZE,
            "filters": [],
            "appliedSearchAggregationFilters": [],
        }
        return scrapy.Request(
            _API,
            method="POST",
            body=json.dumps(body),
            callback=self.parse_page,
            errback=self.errback,
            meta={"skip": skip},
            dont_filter=True,
        )

    async def start(self):
        yield self._request(skip=0)

    def parse_page(self, response):
        skip = response.meta["skip"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("farro_fresh: non-JSON response at skip=%d", skip)
            return

        content = payload.get("content") or []
        if not content:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for c in content:
            price = c.get("sellPrice")
            if price is None:
                price = c.get("originalPrice")
            if price is None:
                continue
            title = c.get("title")
            if not title:
                continue
            uom = c.get("unitOfMeasure")
            name = f"{title} ({uom})" if uom and uom.lower() != "each" else title
            dept = c.get("department")
            cat = c.get("category")
            category = f"{cat} / {dept}" if cat and dept else (cat or dept)
            sku = str(c.get("productSKU") or c.get("id") or "")
            yield {
                "product_id": sku,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "brand": c.get("brand") or None,
                "url": f"https://www.farro.co.nz/shop/product/{c.get('id')}"
                if c.get("id")
                else "https://www.farro.co.nz/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        total = payload.get("totalElements") or 0
        next_skip = skip + _PAGE_SIZE
        if next_skip < total:
            yield self._request(skip=next_skip)

    def errback(self, failure):
        logger.error(
            "farro_fresh: request failed %s — %r", failure.request.url, failure.value
        )
