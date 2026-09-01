"""
Krónan (Iceland) — https://www.kronan.is/.

One of the three big Icelandic grocery chains. The storefront is a Next.js
app; the online-shopping section ("Snjallverslun") is gated behind login,
and the plain `/api/products/` REST list on the backend also returns `[]`
for anonymous callers. Individual product pages (`/vara/<id>-<slug>`) are
public and carry a `schema.org/Product` JSON-LD block, but there is no
public sitemap or category-listing page that enumerates all product URLs
(sitemap-0.xml and server-sitemap.xml only cover static/content pages).

The catalog is walkable anonymously through a *different*, unauthenticated
endpoint used by the site's own search box:

  `GET  https://backend.kronan.is/api/categories`
      -> full category tree (25 top-level, 273 leaves after flattening),
         no auth. Leaf names are Icelandic (e.g. "Mjólk", "Ávextir").

  `POST https://backend.kronan.is/api/products/search/`
      body `{"query": "<text>"}` (note the required trailing slash — the
      bare path 301-redirects and curl_cffi/Scrapy silently downgrades the
      redirected request to GET, which then 405s)
      -> JSON list of products whose *name* matches the query text
         full-text, capped at ~100 rows per call, no auth, no pagination
         (`page`/`pageSize` params are accepted but ignored by the API).

We walk the 273 leaf category names as search queries (`_kronan_is_categories.txt`,
one per line) and de-dupe by product `id` across all queries — this is the
same "keyword pack over an open search endpoint" pattern as other sources
with no true category filter. Each product row already carries `sku`,
`slug`, `price`, `discountedPrice`, and its own `category.name` — no need to
re-fetch the PDP.

Currency ISK, whole krónur (confirmed: `price`/`discountedPrice` are plain
integers/floats with no minor-unit division, matching countries.yaml).

Verified live 2026-09-01: `POST .../search/ {"query":"mjolk"}` -> 200, 73
products, e.g. id 100224198 'MS nýmjólk d-vítamínbætt' ISK 287, category
'Mjólk'. Icelandic letters (á, ð, í, ó, ú, þ, æ, ö) round-trip cleanly
through the JSON API in both directions (query text and returned names),
e.g. 'Ísey skyr próteindrykkur suðrænir ávextir'.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://kronan.is"
SEARCH_URL = "https://backend.kronan.is/api/products/search/"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_kronan_is_categories.txt"


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class KronanIsSpider(scrapy.Spider):
    name = "kronan_is"
    allowed_domains = ["kronan.is", "backend.kronan.is"]
    currency = "ISK"
    language = "is"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids = set()

    async def start(self):
        for query in _load_categories():
            yield scrapy.Request(
                SEARCH_URL,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    # Scrapy's DEFAULT_REQUEST_HEADERS sends Accept-Language: en,
                    # which makes this backend localize category.name to English
                    # while product names (free text, no translation) stay
                    # Icelandic. Override so category matches the declared
                    # source language.
                    "Accept-Language": "is",
                },
                body=json.dumps({"query": query}),
                callback=self.parse_search,
                errback=self.errback,
                meta={"query": query},
                dont_filter=True,
            )

    def parse_search(self, response):
        query = response.meta["query"]
        try:
            rows = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url} query={query}")
            return

        emitted = 0
        for row in rows:
            pid = row.get("id")
            if pid is None or pid in self._seen_ids:
                continue
            name = (row.get("name") or "").strip()
            slug = row.get("slug") or ""
            if not name or not slug:
                continue
            price = row.get("discountedPrice")
            if price is None:
                price = row.get("price")
            if price is None:
                continue
            self._seen_ids.add(pid)
            emitted += 1
            category = (row.get("category") or {}).get("name")
            yield {
                "product_id": str(row.get("sku") or pid),
                "product_name": name[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(row.get("isPublished"))
                and not row.get("temporaryShortage"),
                "url": f"{BASE_URL}/vara/{slug}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        logger.info(
            f"{self.name}: query={query!r} got={len(rows)} new={emitted} "
            f"total_seen={len(self._seen_ids)}"
        )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
