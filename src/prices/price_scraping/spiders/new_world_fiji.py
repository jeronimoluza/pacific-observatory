"""
Spider for New World Fiji (Fiji) - newworld.com.fj.

19-store IGA-affiliated chain. The storefront is an Angular SPA backed by a
Vendure GraphQL API at https://api.newworld.com.fj/shop-api. Vendure's search
plugin is disabled, so the catalogue is walked via the `products` query with
take/skip pagination. Pricing is per-store (channel-scoped): the `vendure-token`
header selects a store channel. We pin the Suva flagship (S0033 — NEWWORLD IGA
Suva, Greig St); without a valid store token the default channel returns no
price. Currency is FJD (confirmed via activeChannel). priceWithTax comes back as
an integer in thousandths of a dollar (the frontend divides by 1000), so
3500 -> FJD 3.50.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://api.newworld.com.fj/shop-api"
_STORE_TOKEN = "S0033"
_PAGE_SIZE = 100
_PRICE_SCALE = 1000
_MAX_PAGES = 400  # safety cap

_QUERY = (
    "query($take:Int!,$skip:Int!){"
    "products(options:{take:$take,skip:$skip}){"
    "totalItems items{id name slug "
    "variants{id sku priceWithTax currencyCode} "
    "collections{name}}}}"
)


class NewWorldFijiSpider(scrapy.Spider):
    name = "new_world_fiji"
    allowed_domains = ["api.newworld.com.fj"]
    currency = "FJD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
    }

    def _page_request(self, page):
        skip = page * _PAGE_SIZE
        body = json.dumps(
            {"query": _QUERY, "variables": {"take": _PAGE_SIZE, "skip": skip}}
        )
        return scrapy.Request(
            _API,
            method="POST",
            body=body,
            callback=self.parse_page,
            meta={"page": page},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "vendure-token": _STORE_TOKEN,
            },
            dont_filter=True,
        )

    async def start(self):
        yield self._page_request(page=0)

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("new_world_fiji: non-JSON response page=%d", page)
            return

        data = (payload.get("data") or {}).get("products") or {}
        items = data.get("items") or []
        if not items:
            return
        logger.info("new_world_fiji page=%d count=%d", page, len(items))

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in items:
            name = p.get("name")
            slug = p.get("slug")
            if not name:
                continue
            category = (
                " > ".join(
                    c.get("name")
                    for c in (p.get("collections") or [])
                    if isinstance(c, dict) and c.get("name")
                )
                or None
            )
            url = f"https://www.newworld.com.fj/product/{slug}" if slug else None
            for v in p.get("variants") or []:
                raw = v.get("priceWithTax")
                if raw is None:
                    continue
                try:
                    price = f"{int(raw) / _PRICE_SCALE:.2f}"
                except (TypeError, ValueError):
                    continue
                yield {
                    "product_id": str(v.get("id") or p.get("id")),
                    "product_name": name.strip(),
                    "price": price,
                    "currency": v.get("currencyCode") or self.currency,
                    "category": category,
                    "url": url,
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }

        if page + 1 < _MAX_PAGES:
            yield self._page_request(page=page + 1)

    def errback(self, failure):
        logger.error(
            "new_world_fiji: request failed %s — %r",
            failure.request.url,
            failure.value,
        )
