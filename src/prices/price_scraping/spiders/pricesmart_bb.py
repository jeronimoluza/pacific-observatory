"""
PriceSmart Barbados — https://www.pricesmart.com/en-BB/category/Groceries/G10D03.

Warehouse-club storefront (Nuxt SPA). The category page ships an empty shell
in raw HTML (zero prices), but the product grid is loaded client-side from a
public Bloomreach Discovery search endpoint that needs no session/cookie:

    POST https://www.pricesmart.com/api/br_discovery/getProductsByKeyword
    body: [{"q": "<CATEGORY_KEY>", "search_type": "category", "start": N,
            "rows": R, "account_id": "7024", "auth_key": "ev7libhybjg5h1d1",
            "domain_key": "pricesmart_bloomreach_io_en", "view_id": "BB", ...}]

`account_id`/`auth_key`/`domain_key` are the client-embedded Bloomreach keys
used by every visitor's browser (not a secret session token) — captured via
a Playwright network trace 2026-09-01 and confirmed replayable cold with
plain curl_cffi, no cookies, no Referer required. Response numFound=947 for
the Groceries node (G10D03), matching the brief's "80 pages of grocery"
(947/12 ≈ 79). Pagination via start/rows was verified to advance (zero
product-id overlap between two consecutive pages).

Prices arrive in `price_BB` as integer minor units (fractionDigits=2) —
divide by 100. Currency is BBD (confirmed both in the JSON payload and by
`storeCurrency`/`vsf-currency` cookies during the Playwright trace) — this
resolves the conflicting USD note from an earlier wave-5 probe of the same
candidate, which never got past the SPA shell to see the real currency.

Product URL pattern confirmed via rendered anchor hrefs:
    /en-bb/product/<slug>/<pid>

Warehouse-club pack sizes (e.g. "2.16 kg", "12 Units") are large multi-unit
packs — normalise per unit downstream before cross-source comparison.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_URL = "https://www.pricesmart.com/api/br_discovery/getProductsByKeyword"
CATEGORY_URL = "https://www.pricesmart.com/en-BB/category/Groceries/G10D03"
CATEGORY_KEY = "G10D03"
ACCOUNT_ID = "7024"
AUTH_KEY = "ev7libhybjg5h1d1"
DOMAIN_KEY = "pricesmart_bloomreach_io_en"
VIEW_ID = "BB"
ROWS = 48
FIELDS = (
    "pid,title,price,brand,slug,skuid,currency,fractionDigits,master_sku,"
    "availability_BB,price_BB,inventory_BB"
)


class PricesmartBbSpider(scrapy.Spider):
    name = "pricesmart_bb"
    allowed_domains = ["pricesmart.com"]
    currency = "BBD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._api_request(0)

    def _api_request(self, start):
        payload = [
            {
                "url": CATEGORY_URL,
                "start": start,
                "q": CATEGORY_KEY,
                "fq": [],
                "search_type": "category",
                "rows": ROWS,
                "account_id": ACCOUNT_ID,
                "auth_key": AUTH_KEY,
                "request_id": int(datetime.now(timezone.utc).timestamp() * 1000),
                "domain_key": DOMAIN_KEY,
                "fl": FIELDS,
                "view_id": VIEW_ID,
            }
        ]
        return scrapy.Request(
            API_URL,
            method="POST",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            callback=self.parse_api,
            errback=self.errback,
            meta={"start": start},
            dont_filter=True,
        )

    def parse_api(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        resp = data.get("response") or {}
        docs = resp.get("docs") or []
        num_found = resp.get("numFound", 0)
        start = response.meta["start"]

        for doc in docs:
            pid = doc.get("pid") or doc.get("master_sku")
            title = (doc.get("title") or "").strip()
            price_minor = doc.get("price_BB")
            if not pid or not title or price_minor is None:
                continue
            fraction_digits = doc.get("fractionDigits", 2)
            price = price_minor / (10**fraction_digits)
            slug = doc.get("slug") or ""
            avail_raw = doc.get("availability_BB")
            available = str(avail_raw).lower() == "true"
            yield {
                "product_id": str(pid),
                "product_name": title[:500],
                "category": "Groceries",
                "price": str(price),
                "currency": doc.get("currency") or self.currency,
                "available": available,
                "url": f"https://www.pricesmart.com/en-bb/product/{slug}/{pid}"
                if slug
                else CATEGORY_URL,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name}: start={start} got={len(docs)} numFound={num_found}")

        next_start = start + ROWS
        if docs and next_start < num_found:
            yield self._api_request(next_start)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
