"""
Spider for Tropicart (Dominica) -- https://tropicart.app/.

Vite/React SPA built on Supabase (Postgres + auto-generated PostgREST API).
The shipped JS bundle (/assets/index-*.js) embeds the Supabase project URL
and its public "anon"-role JWT in plaintext -- this is Supabase's standard,
intended model (row-level security gates access, not key secrecy). We query
the REST endpoint directly with limit/offset pagination; live-checked
2026-08-17: offset=0 and offset=20 return disjoint product ids out of 544
active rows (Prefer: count=exact header), and the bundle's default currency
constant is XCD (matches Dominica's official currency, though individual
stores could in principle price differently).
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://bqjypvuvtcobhjinmwmg.supabase.co/rest/v1/products"
_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJxanlwdnV2dGNvYmhqaW5td21nIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxMzY4MTEsImV4cCI6MjA4ODcxMjgxMX0."
    "jc2Q09OEM0PHUxjEJS8LTzeG96BDfAbuLaByU6HY0pk"
)
_SELECT = "id,name,price,category,unit,status,slug"
_PAGE_SIZE = 100
MAX_PAGES = 20


class TropicartDmSpider(scrapy.Spider):
    name = "tropicart_dm"
    allowed_domains = ["tropicart.app", "supabase.co"]
    currency = "XCD"
    language = "en"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def _request(self, offset: int):
        url = f"{_BASE}?select={_SELECT}&status=eq.active&limit={_PAGE_SIZE}&offset={offset}"
        return scrapy.Request(
            url,
            headers={"apikey": _ANON_KEY, "Authorization": f"Bearer {_ANON_KEY}"},
            callback=self.parse_page,
            meta={"impersonate": "chrome124", "offset": offset},
        )

    async def start(self):
        yield self._request(0)

    def parse_page(self, response):
        offset = response.meta["offset"]
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"tropicart_dm: non-JSON response at offset={offset}")
            return
        if not isinstance(products, list) or not products:
            return
        logger.info(f"tropicart_dm offset={offset} count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, scraped_at)
            if item:
                yield item
        if len(products) >= _PAGE_SIZE and (offset // _PAGE_SIZE + 1) < MAX_PAGES:
            yield self._request(offset + _PAGE_SIZE)

    def _item(self, p: dict, scraped_at: str):
        name = html.unescape(str(p.get("name") or "")).strip()
        price = p.get("price")
        if not name or price is None:
            return None
        slug = p.get("slug")
        return {
            "product_id": str(p.get("id")),
            "product_name": name[:500],
            "category": p.get("category"),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://tropicart.app/product/{slug}"
            if slug
            else "https://tropicart.app/",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
