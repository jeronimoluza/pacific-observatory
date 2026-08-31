"""
Kedo Market (Democratic Republic of Congo) — https://www.kedomarket.com/.

The storefront is a React SPA (Vite bundle, empty `<div id="root">` in the
raw HTML) fronted by Supabase. The bundle
(`/assets/index-B_5QKmX1.js`) embeds a public Supabase anon JWT
(role "anon", ref "esofbvltjrrpcowawyyw") and calls
`.from("products")` via supabase-js, i.e. a plain PostgREST endpoint —
no auth beyond the anon key, which the bundle ships to every visitor by
design. Probed live 2026-08-31: `GET .../rest/v1/products?select=*` with
`apikey`/`Authorization: Bearer <anon>` returns 200 with real listings.

Small marketplace: 99 active listings across 29 independent merchants
(Content-Range header confirms the total), almost entirely fashion
(vetements-femme/homme, chaussures, perruques, accessoires, beaute) with a
handful of electronics — no grocery/food category observed. Each seller
sets their own price and currency; 72 of 99 rows are USD, 27 are CDF —
both are genuine, left unconverted per-row. Locality: Supabase locale is
fr_CD, the site brands itself "Le marché numérique de la RDC" for
"vendeurs congolais", and most listings run in CDF, so this prices DRC
sellers directly rather than a diaspora storefront.

Pagination via PostgREST's `Range` header (0-based, inclusive), walked
until a short page comes back.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SUPABASE_URL = "https://esofbvltjrrpcowawyyw.supabase.co"
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVzb2Zidmx0anJycGNvd2F3eXl3Iiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NjQ4MTA2NTMsImV4cCI6MjA4MDM4NjY1M30."
    "lWcnlRC1SO2BsPHUJe15s1Wd-kTKgSdfIcR-OVxX8sc"
)
PAGE_SIZE = 500
MAX_PAGES = 40  # safety cap; catalog observed at 99 rows


class KedomarketCdSpider(scrapy.Spider):
    name = "kedomarket_cd"
    allowed_domains = ["esofbvltjrrpcowawyyw.supabase.co"]
    currency = "CDF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
    }

    def _headers(self, start: int, end: int) -> dict:
        return {
            "apikey": ANON_KEY,
            "Authorization": f"Bearer {ANON_KEY}",
            "Range-Unit": "items",
            "Range": f"{start}-{end}",
            "Accept": "application/json",
        }

    async def start(self):
        url = (
            f"{SUPABASE_URL}/rest/v1/products"
            "?select=id,name,category,price,currency,is_active"
            "&is_active=eq.true&order=id.asc"
        )
        yield scrapy.Request(
            url,
            callback=self.parse_page,
            headers=self._headers(0, PAGE_SIZE - 1),
            meta={"start": 0},
            errback=self.errback,
        )

    def parse_page(self, response):
        try:
            rows = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON response at {response.url}")
            return
        if not isinstance(rows, list):
            return

        start = response.meta["start"]
        logger.info(f"{self.name}: range start={start} got={len(rows)}")

        for row in rows:
            item = self._item(row)
            if item:
                yield item

        if len(rows) == PAGE_SIZE and (start // PAGE_SIZE) + 1 < MAX_PAGES:
            next_start = start + PAGE_SIZE
            url = (
                f"{SUPABASE_URL}/rest/v1/products"
                "?select=id,name,category,price,currency,is_active"
                "&is_active=eq.true&order=id.asc"
            )
            yield scrapy.Request(
                url,
                callback=self.parse_page,
                headers=self._headers(next_start, next_start + PAGE_SIZE - 1),
                meta={"start": next_start},
                errback=self.errback,
                dont_filter=True,
            )

    def _item(self, row: dict):
        pid = row.get("id")
        name = row.get("name")
        price = row.get("price")
        if not pid or not name or price is None:
            return None
        return {
            "product_id": str(pid),
            "product_name": str(name).strip()[:500],
            "category": row.get("category") or None,
            "price": str(price),
            "currency": row.get("currency") or self.currency,
            "available": bool(row.get("is_active", True)),
            "url": f"https://www.kedomarket.com/produit/{pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
