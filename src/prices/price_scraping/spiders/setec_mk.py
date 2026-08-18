"""
Spider for Setec (North Macedonia) -- https://setec.mk/.

Next.js App Router storefront over a self-hosted Medusa.js commerce
backend; product data is client-rendered (RSC streaming), so neither the
raw category HTML nor /store/products carries prices server-side.

Discovery via Playwright network trace (2026-08-17) found the actual data
source: the product grid is populated client-side by a direct POST to a
Meilisearch instance at search.sp.solslab.dev/indexes/products/search,
authenticated with a search-only Bearer key that ships in the site's own
JS bundle (public by design -- every page load sends it). No WAF/TLS
impersonation needed; plain requests to that endpoint succeed.

Enumerability proven: offset=0 vs offset=60 (limit=60 each) return 60 + 60
distinct product ids, zero overlap; estimatedTotalHits=1000 (Meilisearch's
default hard cap on this index -- the real catalog may be larger, but 1000
is a genuine, walkable slice, not a curated carousel).

Price is MKD (denars, no minor-unit division) from
variants[0].calculated_price.calculated_amount.
"""

import json
from datetime import datetime, timezone

import scrapy

_SEARCH_URL = "https://search.sp.solslab.dev/indexes/products/search"
_SEARCH_KEY = "c0424dab588b8cbbbe0a4809fc10b5f1c0c7d183b5b28ebe799f3fbf583ab358"
_LIMIT = 60
_MAX_OFFSET = 1000


class SetecMkSpider(scrapy.Spider):
    name = "setec_mk"
    allowed_domains = ["setec.mk", "search.sp.solslab.dev"]
    currency = "MKD"
    language = "mk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield self._page_request(0)

    def _page_request(self, offset: int):
        body = {
            "q": "",
            "limit": _LIMIT,
            "offset": offset,
            "filter": "status = 'published' AND is_web_active = 'true'",
        }
        return scrapy.Request(
            _SEARCH_URL,
            method="POST",
            headers={
                "Authorization": f"Bearer {_SEARCH_KEY}",
                "Content-Type": "application/json",
            },
            body=json.dumps(body),
            callback=self.parse_page,
            meta={"offset": offset},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            self.logger.warning(
                f"{self.name}: non-JSON response at offset {response.meta['offset']}"
            )
            return
        hits = data.get("hits") or []
        offset = response.meta["offset"]
        self.logger.info(f"{self.name}: offset={offset} count={len(hits)}")
        for h in hits:
            item = self._item(h)
            if item:
                yield item
        if hits and offset + _LIMIT < _MAX_OFFSET:
            yield self._page_request(offset + _LIMIT)

    def _item(self, h: dict):
        title = (h.get("title") or "").strip()
        variants = h.get("variants") or []
        if not title or not variants:
            return None
        calc = (variants[0].get("calculated_price") or {}).get("calculated_amount")
        if calc is None:
            return None
        handle = h.get("handle") or ""
        return {
            "product_id": h.get("id") or "",
            "product_name": title[:500],
            "category": None,
            "price": str(calc),
            "currency": self.currency,
            "available": True,
            "url": f"https://setec.mk/mk/proizvod/{handle}" if handle else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
