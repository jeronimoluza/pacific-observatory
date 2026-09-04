"""
Spider for Kiwaba Online (Angola) — https://www.kiwaba.online/.

React/Vite SPA (div#root) backed by an open Supabase PostgREST API. The
anon JWT key is embedded in the shipped JS bundle (/assets/index-*.js) and
is meant to be public (Supabase's standard anon-key model — RLS, not
secrecy, gates access). We query the REST endpoint directly with
limit/offset pagination; a live count=exact probe confirmed 286 active
products total (2026-09-04).

category:categories(...) uses PostgREST's foreign-key embedding to resolve
category_id to a readable name in one request. The FK is named explicitly:
products gained a second reference to categories (subcategory_id), so a bare
categories(name) is ambiguous and PostgREST answers 300 PGRST201 -- which
Scrapy's HttpErrorMiddleware drops, so the spider ran to a clean exit with
zero items from 2026-08-12 until this was fixed. HTTPERROR_ALLOW_ALL below
keeps that class of failure loud.
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://aljtwptkvhazymmtiqmx.supabase.co/rest/v1/products"
_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFsanR3cHRrdmhhenltbXRpcW14Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwMzI5NDksImV4cCI6MjA5MjYwODk0OX0."
    "AJH7lvtoDOnpsxjMT-_oEYtoSUevVCuKbA1l5IIU_nQ"
)
_SELECT = "id,name,price,unit,category:categories!products_category_id_fkey(name)"
_PAGE_SIZE = 200
MAX_PAGES = 10


class KiwabaAoSpider(scrapy.Spider):
    name = "kiwaba_ao"
    allowed_domains = ["kiwaba.online", "supabase.co"]
    currency = "AOA"
    language = "pt"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "HTTPERROR_ALLOW_ALL": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, offset: int):
        url = (
            f"{_BASE}?select={_SELECT}&active=eq.true"
            f"&limit={_PAGE_SIZE}&offset={offset}"
        )
        return scrapy.Request(
            url,
            headers={"apikey": _ANON_KEY},
            callback=self.parse_page,
            meta={"offset": offset},
        )

    async def start(self):
        yield self._request(0)

    def parse_page(self, response):
        offset = response.meta["offset"]
        if response.status != 200:
            logger.error(
                f"kiwaba_ao: HTTP {response.status} at offset={offset}: "
                f"{response.text[:300]}"
            )
            return
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"kiwaba_ao: non-JSON response at offset={offset}")
            return
        if not isinstance(products, list) or not products:
            return
        logger.info(f"kiwaba_ao offset={offset} count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            cat = p.get("category") or {}
            yield {
                "product_id": str(p.get("id")),
                "product_name": html.unescape(str(p.get("name") or "")).strip()[:500],
                "category": cat.get("name") if isinstance(cat, dict) else None,
                "price": str(p.get("price")),
                "currency": self.currency,
                "available": True,
                "url": f"https://www.kiwaba.online/#{p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if len(products) >= _PAGE_SIZE and (offset // _PAGE_SIZE + 1) < MAX_PAGES:
            yield self._request(offset + _PAGE_SIZE)
