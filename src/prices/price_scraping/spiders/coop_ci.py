"""
Channel Islands Co-operative Society — https://shop.channelislands.coop/.

The Channel Islands' first price source of any kind (`channel_islands` had
zero manifests before this pass). The Co-op is the islands' dominant grocer
and runs the only real online grocery on either island.

The storefront is a **Flutter web app** ("eLoyalty Customer App", OGS =
Online Grocery Shopping) compiled to canvas — there is no DOM product markup
at all, so neither an HTML spider nor a Playwright DOM scrape can see a
single product. Playwright was used once, to *discover* the backend; the
spider then talks to that backend over plain HTTP and never runs a browser.

    GET https://ogs.channelislands.coop/api/stores
    GET https://ogs.channelislands.coop/api/stores/<id>/products?per_page=100&page=<N>

The API needs a Laravel Sanctum bearer token. It is not a user credential:
a single anonymous app token is compiled into `main.dart.js` and shipped to
every visitor, granting exactly the read-only catalogue access a browser
gets. The spider re-extracts it from the bundle on each run so a rotation
does not silently zero the crawl, falling back to the observed literal.

Two stores, both inside the `channel_islands` slug:

    id=1  Jsy - Millennium Park Grand Marché   (Jersey)   5,058 products
    id=2  Gsy - St Martin Grand Marché         (Guernsey) 4,687 products

BOTH are scraped, because they are genuinely different price points rather
than one catalogue served twice: of 110 products sharing an id across the
two stores, **108 carried different prices** (Guernsey systematically
cheaper — e.g. Nescafé Gold Blend 190g £10.85 Jsy vs £10.30 Gsy, Rice
Krispies 430g £3.55 vs £3.35). Product ids are reused across stores, so
identity is (store, id) and the emitted URL carries `?store=` — without it
`DuplicationPipeline` (which dedups on `item['url']`) would drop the
Guernsey copy of every shared product.

MINOR UNITS: `price` is an integer in **pence**, not pounds — the record
carries `price: 3150` alongside `unit_price_text: "£31.50 per ITEM"`. It is
divided by 100 here. Currency is GBP for both islands (matches
countries.yaml; Jersey/Guernsey pounds are at par with sterling).

Verified live 2026-09-01: store 1 total=5058 (51 pages), store 2 total=4687
(47 pages); page 1 and page 2 returned disjoint id sets for both stores,
confirming real pagination rather than a repeated first page.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SHOP_URL = "https://shop.channelislands.coop"
API_BASE = "https://ogs.channelislands.coop"
BUNDLE_URL = f"{SHOP_URL}/main.dart.js"

# Anonymous app token observed in main.dart.js on 2026-09-01. Used only if
# the runtime extraction below fails.
FALLBACK_TOKEN = "1|laxUtQn8bc3GVltvYLXRqhzRiRQzMaXeOANBaUx62a8b8ab6"
_TOKEN_RE = re.compile(r"\d+\|[A-Za-z0-9]{40,60}")

STORE_IDS = (1, 2)
PER_PAGE = 100
MAX_PAGES = 80  # safety cap; largest store is 51 pages at PER_PAGE=100


class CoopCiSpider(scrapy.Spider):
    name = "coop_ci"
    allowed_domains = ["channelislands.coop", "ogs.channelislands.coop"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = FALLBACK_TOKEN

    async def start(self):
        yield scrapy.Request(
            BUNDLE_URL,
            callback=self.parse_bundle,
            errback=self.errback,
            dont_filter=True,
        )

    def parse_bundle(self, response):
        """Pull the anonymous bearer token out of the Flutter bundle."""
        match = _TOKEN_RE.search(response.text)
        if match:
            self.token = match.group(0)
            logger.info(f"{self.name}: token extracted from bundle")
        else:
            logger.warning(f"{self.name}: no token literal in bundle — using fallback")
        for store in STORE_IDS:
            yield self._api_request(store, 1)

    def _api_request(self, store, page):
        return scrapy.Request(
            f"{API_BASE}/api/stores/{store}/products"
            f"?per_page={PER_PAGE}&page={page}",
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                "Origin": SHOP_URL,
                "Referer": f"{SHOP_URL}/",
            },
            meta={"store": store, "page": page},
            dont_filter=True,
        )

    def parse_api(self, response):
        store = response.meta["store"]
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        products = payload.get("data") or []
        meta = payload.get("meta") or {}
        found = 0

        for product in products:
            name = (product.get("description") or "").strip()
            pence = product.get("price")
            pid = product.get("id")
            if not name or pid is None or not pence:
                continue
            try:
                price = f"{int(pence) / 100:.2f}"
            except (TypeError, ValueError):
                continue

            categories = product.get("categories") or {}
            breadcrumb = categories.get("lvl1") or categories.get("lvl0") or []
            found += 1
            yield {
                "product_id": f"{store}-{pid}",
                "product_name": name[:500],
                "category": breadcrumb[0] if breadcrumb else "",
                "price": price,
                "currency": self.currency,
                "available": bool(product.get("available_for_customers", True)),
                "url": f"{SHOP_URL}/product-details/{pid}?store={store}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: store={store} page={page} items={len(products)} "
            f"yielded={found} total={meta.get('total')}"
        )

        last_page = meta.get("last_page") or 0
        if products and page < min(last_page, MAX_PAGES):
            yield self._api_request(store, page + 1)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
