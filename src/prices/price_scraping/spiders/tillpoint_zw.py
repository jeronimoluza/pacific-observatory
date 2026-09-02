"""
TillPoint (Zimbabwe) — https://tillpoint.co.zw/.

React Native / Expo web app. The rendered HTML is a static shell for every
route ("/", "/product/<slug>" all return the identical ~52KB document) —
all catalog data is fetched client-side, so there is no HTML surface to
scrape. The Expo web bundle
(/_expo/static/js/web/entry-*.js) embeds the app's Supabase project
config (extra.supabaseUrl / extra.supabaseAnonKey inside the Expo
manifest JSON) plus a set of `.from("<table>")` calls, one of which is
`products`. That anon key is a public, RLS-scoped read key (the same one
shipped to every browser/app instance) and grants a plain PostgREST GET
against:

    GET {supabaseUrl}/rest/v1/products
        ?select=id,name,slug,price,currency,is_available,categories(name)
        &order=created_at.asc

Paginated with the standard PostgREST `Range: <start>-<end>` header
(page size 200); Content-Range in the response ("0-199/345") gives the
total, so the walk stops once start >= total instead of guessing a page
count. Measured total 2026-08-31: 345 products across 9 categories
(Groceries, butchery, Fruit & Veg, Hardware & Tools, Building Materials,
Farm Inputs, Solar & Electrical, Agri Equipment, General Merchandise) —
a wide, non-food-only catalog. Prices are plain numeric (USD) with no
entity-encoding.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SUPABASE_URL = "https://ojyqiomlnbikncdpbvmh.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6"
    "Im9qeXFpb21sbmJpa25jZHBidm1oIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQzNTMx"
    "MjEsImV4cCI6MjA3OTkyOTEyMX0.qC7KvKMfmpDO1t0sGECVHJ6B90PmeDZ5AtzJTTqmq6o"
)
SELECT = "id,name,slug,price,currency,is_available,categories(name)"
PAGE_SIZE = 200
BASE_URL = "https://tillpoint.co.zw"


class TillpointZwSpider(scrapy.Spider):
    name = "tillpoint_zw"
    allowed_domains = ["tillpoint.co.zw", "ojyqiomlnbikncdpbvmh.supabase.co"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _api_request(self, start):
        end = start + PAGE_SIZE - 1
        return scrapy.Request(
            f"{SUPABASE_URL}/rest/v1/products?select={SELECT}&order=created_at.asc",
            callback=self.parse_api,
            errback=self.errback,
            headers={
                "apikey": ANON_KEY,
                "Authorization": f"Bearer {ANON_KEY}",
                "Range-Unit": "items",
                "Range": f"{start}-{end}",
                "Prefer": "count=exact",
                "Accept": "application/json",
            },
            meta={"start": start},
            dont_filter=True,
        )

    async def start(self):
        yield self._api_request(0)

    def parse_api(self, response):
        start = response.meta["start"]
        try:
            rows = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        for row in rows:
            name = (row.get("name") or "").strip()
            price = row.get("price")
            slug = row.get("slug") or ""
            pid = row.get("id") or ""
            if not name or price is None:
                continue
            category = (row.get("categories") or {}).get("name") or ""
            yield {
                "product_id": pid,
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": row.get("currency") or self.currency,
                "available": bool(row.get("is_available", True)),
                "url": f"{BASE_URL}/product/{slug}"
                if slug
                else f"{BASE_URL}/product/{pid}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        content_range = response.headers.get(b"Content-Range", b"").decode()
        total = None
        if "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[-1])
            except ValueError:
                total = None

        logger.info(
            f"{self.name}: start={start} got={len(rows)} content_range={content_range}"
        )

        next_start = start + PAGE_SIZE
        if rows and (total is None or next_start < total):
            yield self._api_request(next_start)

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
