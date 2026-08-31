"""
Nasser Pharmacy (Bahrain) — https://www.nasserpharmacy.com/.

Bare React SPA shell (no server-rendered content at all — even the
product-detail route returns the same ~6KB app shell). The backend is a
Laravel API on a separate host (`newapi.nasserpharmacy.com`) hardcoded in
the main JS bundle, gated by a client-exposed static header baked into the
bundle's RTK-Query base config:

    Nasser: eyJ0b2tlbiI6ImQ2ZjU4ZDM4ZGU2ZDVhNDBhODExODg5ZjJkNTI0MDViIiwiaWQiOiIxNTI0NTYwMzgyNTA2In0

(same class of trap as a public Supabase anon key — it ships to every
browser, so using it here is reading what the site already serves, not
bypassing anything). The bundle's `getProducts` RTK endpoint hits:

    POST /newproduct-list?category_id=&filter_manufacturer_id=&lang=en
         &currency_code=BHD&start=<N>&in_stock=0&sort=&order=&merchant_id=

returning 15 products/page plus a `total_products` count (20,695 at probe
time); `start` is walked in steps of 15 until `start` reaches
`total_products` (a `MAX_PAGES` safety cap is also enforced). A page
occasionally returns fewer than 15 rows without the catalog being
exhausted (start=75 returned 14 once, start=90 went straight back to 15,
likely a product filtered server-side mid-listing) — the walk does NOT
stop on a short page, only on `total_products` or an empty page. Each row
already carries `price_symbol: "BHD"`, `decimal_places: 3` and a plain
decimal `price` — no rescaling needed. `+97317720800` in the site's
schema.org markup and the BHD pricing confirm this is genuinely the
Bahrain storefront, not a shared GCC catalog.

Rows with `status != 1`, `forcedisable`, `stock_count <= 0`, or a missing
name/price are dropped. This is a pharmacy/health & beauty catalog
(medicines, cosmetics, vitamins) — not food, added alongside the two
grocery sources already onboarded for this country.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.nasserpharmacy.com"
API_URL = "https://newapi.nasserpharmacy.com/newproduct-list"
PAGE_SIZE = 15
MAX_PAGES = 1500  # safety cap: 1500 * 15 = 22,500, comfortably above the ~20.7k catalog

_HEADERS = {
    "Nasser": "eyJ0b2tlbiI6ImQ2ZjU4ZDM4ZGU2ZDVhNDBhODExODg5ZjJkNTI0MDViIiwiaWQiOiIxNTI0NTYwMzgyNTA2In0",
    "MOBILEOS": "REACT",
    "APPVERSION": "1",
    "DCCOMICS": "95",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}


class NasserPharmacyBhSpider(scrapy.Spider):
    name = "nasser_pharmacy_bh"
    allowed_domains = ["nasserpharmacy.com"]
    currency = "BHD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._api_request(0)

    def _api_request(self, start):
        url = (
            f"{API_URL}?category_id=&filter_manufacturer_id=&lang={self.language}"
            f"&currency_code={self.currency}&start={start}&in_stock=0&sort=&order=&merchant_id="
        )
        return scrapy.Request(
            url,
            method="POST",
            body="",
            headers=_HEADERS,
            callback=self.parse_page,
            errback=self.errback,
            meta={"start": start},
            dont_filter=True,
        )

    def parse_page(self, response):
        start = response.meta["start"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON at start={start}")
            return

        products = payload.get("data") or []
        total = payload.get("total_products")
        found = 0

        for product in products:
            if product.get("status") != 1 or product.get("forcedisable"):
                continue
            if (product.get("stock_count") or 0) <= 0:
                continue
            name = (product.get("name") or "").strip()
            price = product.get("price")
            if not name or not price or float(price) == 0:
                continue
            if product.get("price_symbol") != self.currency:
                continue

            found += 1
            alias = product.get("product_alias") or ""
            yield {
                "product_id": str(
                    product.get("product_id") or product.get("sku") or ""
                ),
                "product_name": name[:500],
                "category": "pharmacy",
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"{BASE_URL}/bh-en/product-details/{alias}"
                if alias
                else response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            f"{self.name}: start={start} got={len(products)} yielded={found} total_products={total}"
        )

        next_start = start + PAGE_SIZE
        # A page occasionally returns fewer than PAGE_SIZE rows (a product
        # mid-listing gets filtered server-side) without that meaning the
        # catalog is exhausted -- start=75 returned 14 rows once, start=90
        # went straight back to 15. Rely on total_products as the real stop
        # signal, not a short page.
        if (
            products
            and (total is None or next_start < total)
            and (next_start // PAGE_SIZE) < MAX_PAGES
        ):
            yield self._api_request(next_start)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
