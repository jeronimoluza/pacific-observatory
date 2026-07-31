"""
Spider for Basic Home Mart (Timor-Leste) — https://basichomemart.com.

Vue3 SPA storefront (Cloudflare-fronted) backed by a public JSON API at
/dev-api/api/products/list?page=N&pageSize=M returning
{"data":{"total","pages","list":[{id,name,price,category,uom,...}]}}.
Prices are quoted in USD (Timor-Leste uses USD). We paginate the API until
the last page is reached.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://basichomemart.com"
_API = _BASE + "/dev-api/api/products/list"
_PAGE_SIZE = 50


class BasicHomemartSpider(scrapy.Spider):
    name = "basic_homemart"
    allowed_domains = ["basichomemart.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {"Accept": "application/json"},
    }

    async def start(self):
        yield self._page_request(page=1)

    def _page_request(self, page):
        return scrapy.Request(
            f"{_API}?page={page}&pageSize={_PAGE_SIZE}",
            callback=self.parse_page,
            meta={"page": page},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("basic_homemart: non-JSON response p%d", page)
            return

        data = payload.get("data") or {}
        products = data.get("list") or []
        if not products:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("salePrice")
            if price is None:
                price = p.get("price")
            if price is None:
                continue
            name = p.get("name")
            if not name:
                continue
            pid = str(p.get("id", ""))
            uom = p.get("uom")
            full_name = f"{name} ({uom})" if uom else name
            yield {
                "product_id": pid,
                "product_name": full_name,
                "price": price,
                "currency": self.currency,
                "category": p.get("category") or None,
                "url": f"{_BASE}/product/{pid}" if pid else _BASE,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        pages = data.get("pages") or 0
        if page < pages:
            yield self._page_request(page=page + 1)

    def errback(self, failure):
        logger.error(
            "basic_homemart: request failed %s — %r",
            failure.request.url,
            failure.value,
        )
