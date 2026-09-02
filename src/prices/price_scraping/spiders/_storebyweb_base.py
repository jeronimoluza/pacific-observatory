"""
Shared base class for "storebyweb" (WebCart) grocery e-commerce storefronts.

Several Bahamian AML Foods Ltd. chains (Solomon's Fresh Market / Harbour Bay,
Cost Right Nassau, Exuma Markets) run their online-ordering storefronts on a
white-label Vue SPA hosted at "<retailer>.storebyweb.com/s/<STORE_CODE>/".
The SPA shell itself carries no product data, but its browse/search calls
hit a plain JSON POST endpoint:

    POST /s/<STORE_CODE>/api/b   {"pn": <page, 1-based>, "ps": <page size>, "facets": {}}
    -> {"totalCount": N, "items": [{"id","name","actualPrice","department",
                                     "outOfStock","discontinued", ...}]}

`pn` is honoured (verified: 5 consecutive 100-row pages returned 500 fully
distinct ids on the Harbour Bay tenant, zero overlap). Pagination stops when
a page returns fewer than `ps` items or an empty list. actualPrice is the
price actually charged (suggestedPrice is a separate/unused MSRP field that
is frequently 0.0).

The SPA's item-detail route `/i/<id>` is server-side rendered for SEO: the
page's own <title>/og:title carries the real product name, so it makes a
valid, auditable, per-row product URL even though the rest of the SPA is
client-rendered.

Subclasses set: name, allowed_domains, BASE_HOST (e.g.
"harborbaymarkets.storebyweb.com"), STORE_CODE (e.g. "1000-19"), currency,
language.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

PAGE_SIZE = 100
MAX_PAGES = 500  # safety cap


class StorebywebBaseSpider(scrapy.Spider):
    name = None
    BASE_HOST: str = ""
    STORE_CODE: str = ""

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    @property
    def store_url(self) -> str:
        return f"https://{self.BASE_HOST}/s/{self.STORE_CODE}"

    async def start(self):
        yield self._page_request(1)

    def _page_request(self, page: int):
        return scrapy.Request(
            f"{self.store_url}/api/b",
            method="POST",
            body=json.dumps({"pn": page, "ps": PAGE_SIZE, "facets": {}}),
            headers={
                "Content-Type": "application/json",
                "Referer": f"{self.store_url}/",
            },
            meta={"impersonate": "chrome124", "page": page},
            callback=self.parse_page,
            errback=self.errback,
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        page = response.meta["page"]
        items = data.get("items") or []
        total = data.get("totalCount")
        logger.info(f"{self.name}: page={page} got={len(items)} totalCount={total}")
        for it in items:
            row = self._item(it)
            if row:
                yield row
        if items and len(items) >= PAGE_SIZE and page < MAX_PAGES:
            yield self._page_request(page + 1)

    def _item(self, it: dict):
        item_id = it.get("id")
        name = (it.get("name") or "").strip()
        price = it.get("actualPrice")
        if not item_id or not name or price is None or price <= 0:
            return None
        return {
            "product_id": item_id,
            "product_name": name[:500],
            "category": it.get("department"),
            "price": str(price),
            "currency": self.currency,
            "available": not (it.get("outOfStock") or it.get("discontinued")),
            "url": f"{self.store_url}/i/{item_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
