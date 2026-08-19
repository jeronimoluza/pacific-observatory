"""
Spider for Yombouna (Senegal) — https://yombouna.sn/.

SvelteKit SPA shell exposing PUBLIC_SUPABASE_URL + PUBLIC_SUPABASE_ANON_KEY
inline in the homepage's bootstrap `<script>` block (the site's own
hydration payload, not a hidden bundle — meant to be public per Supabase's
anon-key model). Backend is a wide-open Supabase PostgREST `products` table
with category/subcategory as plain string columns already, so no join is
needed. A count=exact probe confirmed 1,677 total rows live.

This replaces the shard's original WooCommerce guess, which 404s — the real
backend is this Supabase table.
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://obyteclxfidycfrqklbz.supabase.co/rest/v1/products"
_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ieXRlY2x4ZmlkeWNmcnFrbGJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTUyNTAxODksImV4cCI6MjA3MDgyNjE4OX0."
    "FS0FoXj4pYsaOWftkcLn8HIFFomSSbzhz1YwUCJeaz0"
)
_SELECT = "id,name,price,category,subcategory,stock"
_PAGE_SIZE = 500
MAX_PAGES = 20


class YombounaSnSpider(scrapy.Spider):
    name = "yombouna_sn"
    allowed_domains = ["yombouna.sn", "supabase.co"]
    currency = "XOF"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, offset: int):
        url = f"{_BASE}?select={_SELECT}&limit={_PAGE_SIZE}&offset={offset}"
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
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"yombouna_sn: non-JSON response at offset={offset}")
            return
        if not isinstance(products, list) or not products:
            return
        logger.info(f"yombouna_sn offset={offset} count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            cat_parts = [c for c in (p.get("category"), p.get("subcategory")) if c]
            yield {
                "product_id": str(p.get("id")),
                "product_name": html.unescape(str(p.get("name") or "")).strip()[:500],
                "category": " > ".join(cat_parts) if cat_parts else None,
                "price": str(p.get("price")),
                "currency": self.currency,
                "available": bool(p.get("stock", True)),
                "url": f"https://yombouna.sn/#{p.get('id')}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if len(products) >= _PAGE_SIZE and (offset // _PAGE_SIZE + 1) < MAX_PAGES:
            yield self._request(offset + _PAGE_SIZE)
