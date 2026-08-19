"""
Shared base class for NCR Freshop storefronts.

Freshop is a hosted grocery catalog API (api.freshop.ncrcloud.com). The
tenant identity is the ``app_key`` query param; a tenant may run several
physical stores (``store_id``), each with its own distinct catalog and
pricing (verified live: Cost-U-Less's four island stores under app_key
``cost_u_less`` return different item counts and different SKUs per
``store_id`` — this is NOT one catalog duplicated across countries).

``/2/products`` hard-caps ``limit`` at 100 regardless of what is requested,
but (unlike the walter_mart tenant used by ``waltermart.py``) it DOES honor
``skip`` for these tenants — verified live by comparing ``skip=0`` vs
``skip=3`` results. So we walk the whole catalog with a plain
``limit=100&skip=N`` page-by-page loop instead of department-sharding.

The ``price`` field is a display string that carries the store's price
symbol (e.g. ``"$2.69"``, ``"ƒ5,99"``) — that symbol is often the only live
signal for which currency a store actually prices in when Freshop provides
no ``currency_code`` field on the product payload. Subclasses set an
explicit ``currency`` regardless; check it against the symbol before
trusting a shard's assumed currency.

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_BASE = "https://api.freshop.ncrcloud.com"
_PRODUCTS = _BASE + "/2/products"
_PAGE_SIZE = 100


class FreshopBaseSpider(scrapy.Spider):
    # Subclasses MUST set: name, allowed_domains, currency, language,
    # APP_KEY, STORE_ID.
    name = None
    allowed_domains = ["api.freshop.ncrcloud.com"]
    APP_KEY: str = ""
    STORE_ID: str = ""
    MAX_PAGES = 2000  # safety cap (limit=100 -> up to 200k items)

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        # See waltermart.py: curl_cffi impersonation SSL-errors against this
        # host; the plain Twisted handler negotiates TLS cleanly. The API
        # 403s a non-browser UA, so CustomUserAgentMiddleware stays enabled.
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.8,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        yield self._page_request(0)

    def _page_request(self, skip: int):
        return scrapy.Request(
            f"{_PRODUCTS}?app_key={self.APP_KEY}&limit={_PAGE_SIZE}"
            f"&skip={skip}&store_id={self.STORE_ID}&sort=id",
            callback=self.parse_page,
            meta={"skip": skip},
            headers={"Accept": "application/json"},
        )

    def parse_page(self, response):
        skip = response.meta["skip"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"{self.name}: non-JSON response at skip={skip}")
            return

        items = payload.get("items") or []
        total = payload.get("total") or 0
        logger.info(f"{self.name}: skip={skip} count={len(items)} total={total}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            item = self._item(it, scraped_at)
            if item:
                yield item

        next_skip = skip + _PAGE_SIZE
        if (
            len(items) >= _PAGE_SIZE
            and next_skip < total
            and next_skip < self.MAX_PAGES * _PAGE_SIZE
        ):
            yield self._page_request(next_skip)

    def _item(self, it: dict, scraped_at: str):
        name = it.get("name")
        price = it.get("unit_price")
        if not name or price is None:
            return None
        return {
            "product_id": it.get("upc") or str(it.get("id", "")),
            "product_name": name,
            "category": self._category_from_url(it.get("canonical_url")),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": it.get("canonical_url") or "",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _category_from_url(canonical_url):
        if not canonical_url:
            return None
        m = re.search(r"/shop/(.+?)/[^/]+/p/\d+", canonical_url)
        if not m:
            return None
        parts = [p.replace("_", " ").strip() for p in m.group(1).split("/") if p]
        return " > ".join(parts) if parts else None

    def errback(self, failure):
        logger.error(
            f"{self.name}: request failed {failure.request.url} — {failure.value!r}"
        )

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Live scrape
    # (_item, above) reads the `/2/products` JSON API; archives only hold
    # the human-facing storefront page, a different surface -- and Freshop's
    # storefront is a WordPress-theme shell that React-hydrates its catalog
    # client-side, so a department page (`/shop/<dept>/d/<id>`) as Common
    # Crawl actually archives it carries NO server-rendered product data at
    # all (confirmed on costuless_sx/costuless_ky: 170/170 of their archived
    # URLs are `/d/` department shells, 0 are `/p/` product pages -- a real
    # coverage gap in what got crawled, not a parsing gap). Genuine
    # product-detail pages (`/p/<id>`, seen on superfoodplaza_aw) DO render
    # a standard schema.org Product node server-side, so the shared
    # archived-page tiers are the whole implementation here -- no bespoke
    # DOM walk needed.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Freshop storefront product-detail page.

        Pure/stateless: no Scrapy Response, no network, no class state.
        Yields 0 or more rows; yields nothing for a department/category
        shell (no product markup) or a product with no price node. Does NOT
        stamp `scraped_at_utc` -- the backfiller stamps the snapshot time.
        """
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row
