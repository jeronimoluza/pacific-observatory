"""
Salonebly / "Yu Don Bay - VLN Solutions" (Sierra Leone) --
https://salonebly.com/

A general online store (FleetCart, an open-source Laravel/Vue commerce
platform) selling electronics, cars, building material, clothing --
AND a large "food-beverages" category of genuinely retail/packaged
goods: bottled spirits and wine, carton/bag staples (Spaghetti, Frozen
Chicken Legs Carton 10Kg, Garlic Carton, Flour 25Kg Bag, Bulger 25Kg
Bag). channel: marketplace reflects the cross-division catalogue (this
one storefront, not third-party sellers -- FleetCart is single-vendor
software here, but the category mix matches the "Cross-division retail"
channel bucket better than any food-specific value).

SCOPING DECISION, made deliberately: the site ALSO has "food", "drinks",
"hot-beverages", "rice", "pasta", "biryani", "naan", "pizza" etc.
categories, but sampling those (2026-09-11) showed they are dominated by
PREPARED RESTAURANT ITEMS (Grilled Prawns, Deep Fried Chicken Wings,
Cappuccino, Tomato Pulao, Veg Pulao) -- COICOP division 11
(restaurants), out of scope for the 01/02 coverage grid this onboarding
pass targets. Only "food-beverages" (retail/packaged: bottled spirits,
wine, carton/bag staples) is crawled; the restaurant-menu categories are
deliberately left uncrawled.

DISCOVERY: FleetCart's category listing page
(/categories/<slug>/products) is a Vue SPA shell -- plain `requests`
returns 0 products in the rendered HTML. Playwright network trace found
the page making a plain GET to itself
(`/products?category=<slug>&...&page=N`) with header
`X-Requested-With: XMLHttpRequest`, which returns clean JSON (verified
working via plain `requests`, no Playwright/impersonation needed at
collection time).

ENUMERABILITY: MEASURED 2026-09-11, category=food-beverages, perPage=30
-> total=157, page1 vs page2 item ids fully disjoint.

PRICE: uses `selling_price.amount` (post-special-price, what a buyer
actually pays), not `price.amount` (list/pre-discount price).

CURRENCY: SLE, read directly from `selling_price.currency` in the
payload -- matches countries.yaml's Sierra Leone default (post-2022
redenomination code).
"""

import logging

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://salonebly.com"
CATEGORY = "food-beverages"
PAGE_SIZE = 30
MAX_PAGES = 30


class SaloneblySlSpider(scrapy.Spider):
    name = "salonebly_sl"
    allowed_domains = ["salonebly.com"]
    currency = "SLE"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        # The project-wide RandomBrowserMiddleware forces curl_cffi TLS
        # impersonation on every request by default (settings.py:45). That
        # path does not forward this spider's custom `X-Requested-With`
        # header to the FleetCart backend (confirmed 2026-09-11: with
        # impersonation on, the endpoint returns the SPA shell HTML, not
        # JSON, even though plain `requests` with the same header returns
        # clean JSON) -- so this spider opts out and uses the standard
        # Twisted HTTP11 handler instead. The site has no WAF (plain HTTP
        # already works), so there is no TLS-fingerprint reason to need
        # impersonation here.
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
    }

    def _url(self, page: int) -> str:
        return (
            f"{BASE}/products?query=&brand=&category={CATEGORY}&tag="
            f"&fromPrice=0&toPrice=1000000&sort=latest"
            f"&perPage={PAGE_SIZE}&page={page}"
        )

    def start_requests(self):
        yield scrapy.Request(
            self._url(1),
            headers=self._ajax_headers(),
            callback=self.parse_page,
            meta={"page": 1},
        )

    def _ajax_headers(self) -> dict:
        # Scrapy's default Accept header ("text/html,...") makes Laravel's
        # wantsJson() return false even with X-Requested-With set -- both
        # headers are required to get the JSON branch (confirmed 2026-09-11).
        return {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
        }

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"salonebly_sl: non-JSON response at page {response.meta['page']}")
            return
        block = (data or {}).get("products") or {}
        items = block.get("data") or []
        page = response.meta["page"]
        logger.info(f"salonebly_sl page={page} count={len(items)} total={block.get('total')}")

        for it in items:
            name = it.get("name")
            sp = it.get("selling_price") or {}
            price = sp.get("amount")
            if not name or price is None:
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            slug = it.get("slug") or it.get("id")
            yield {
                "product_id": str(it.get("id")),
                "product_name": str(name).strip()[:500],
                "price": str(price),
                "currency": sp.get("currency") or self.currency,
                "category": CATEGORY,
                "url": f"{BASE}/products/{slug}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if items and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                self._url(nxt),
                headers=self._ajax_headers(),
                callback=self.parse_page,
                meta={"page": nxt},
            )
