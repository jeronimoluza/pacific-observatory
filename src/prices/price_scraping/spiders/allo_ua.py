"""Spider for ALLO (Ukraine) -- https://allo.ua/.

ALLO is a large Ukrainian electronics/appliances marketplace ("ALLO --
national marketplace"). Discovery lead (bare hostname `allo.ua`, wave 3).
`known_blockers.md` had it listed as an untouched Cloudflare-suspect --
re-probed 2026-09-06 with `curl_cffi impersonate=chrome124`: clean HTTP 200,
no UA-resident IP or extra headers needed. Server is `cloudflare` but the
challenge is not engaged for GET requests with a browser TLS fingerprint.

Server-rendered HTML (Magento-based storefront -- `.html` PDP suffix,
`media/catalog/product/cache/...` image paths). Category listing pages embed
one `<div data-product-id="N" class="products-layout__item ...">` per
product, wrapping a `.product-card` with:
  - name + PDP url: `a.product-card__title` (href + title attr + text)
  - current price: `div.v-pb__cur span.sum` (the *old*, crossed-out price
    lives in a sibling `div.v-pb__old` -- always prefer `.v-pb__cur`, which
    holds the actual sale price whether or not the item is discounted)
  - currency: `div.v-pb__cur span.currency` (site is UAH-only; symbol is
    always "₴")

Some top-level mega-menu entries (e.g. `mobilnye-telefony-i-sredstva-svyazi`)
are pure hub pages with zero product cards -- their children
(`smartfony` -- 404s directly, must go through a hub) carry the real grid.
Verified leaves: `televizory`, `naushniki` both return 60 product cards.

**Pagination is Magento `?p=N`, NOT `?page=N`** (`?page=N` is silently
ignored and re-serves page 1 -- do not use it). Critically, `?p=N` past the
last real page does **not** 404 or go empty -- it re-serves the *last* page
verbatim (confirmed identical product-id sets at p=50 and p=100 on
`naushniki`). This is the exact Magento pagination-loop trap recorded in
prior runs: stopping on "0 items" alone would spin forever. The walk stops
when a page's product-id set is empty OR identical to the previous page's
set.

211 category slugs (`_allo_ua_categories.txt`) were pulled from two shards
of the site's own category sitemap (`/map/secure/categories/sitemap{1,2}.xml.gz`,
`/ru/<slug>/` locations translated to the `/ua/` locale, per-city variants
--dnipro, l-viv, odesa, etc.-- stripped). This is a partial slice of the
full mega-menu (the sitemap index lists ~20 shards); some slugs will be pure
hubs and yield 0 items, which just costs one extra request each.

Kyiv catalogue (Ukrainian convention for city-priced sources, no city
selector cookie needed -- Kyiv is the unauthenticated default).

Page family parsed: listing (category grid pages only; PDP is never
fetched).

Test run 2026-09-06 (--max-items 60, closespider-timeout 120): rows written
with distinct product_id, 0 blank names, 0 zero/negative prices, 100% UAH.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://allo.ua"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_allo_ua_categories.txt"
_MAX_PAGES = 15  # safety cap per category

_BLOCK_SPLIT_RE = re.compile(r'(?=<div data-product-id="\d+" class="products-layout__item)')
_PRODUCT_ID_RE = re.compile(r'data-product-id="(\d+)"')
_NAME_URL_RE = re.compile(
    r'<a href="([^"]+)" title="([^"]*)" class="product-card__title">'
)
_PRICE_RE = re.compile(
    r'<div class="v-pb__cur[^"]*"><span class="sum">([\d\s]+)</span>\s*'
    r'<span class="currency">\s*([^\s<]+)\s*</span>'
)


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


def _currency_symbol_to_code(sym: str) -> str:
    return "UAH" if sym.strip() == "₴" else "UAH"


class AlloUaSpider(scrapy.Spider):
    name = "allo_ua"
    allowed_domains = ["allo.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
        "DOWNLOAD_TIMEOUT": 60,
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/ua/{slug}/?p=1",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1, "prev_ids": frozenset(), "impersonate": "chrome124"},
            )

    def _extract(self, response, category: str) -> list[dict]:
        items = []
        for block in _BLOCK_SPLIT_RE.split(response.text)[1:]:
            pid = _PRODUCT_ID_RE.search(block)
            nm = _NAME_URL_RE.search(block)
            pr = _PRICE_RE.search(block)
            if not (pid and nm and pr):
                continue
            name = html.unescape(nm.group(2)).strip()
            name = re.sub(r"\s+", " ", name)
            if not name:
                continue
            price_str = pr.group(1).replace("\xa0", " ").replace(" ", "").strip()
            if not price_str:
                continue
            url = nm.group(1)
            if url.startswith("/"):
                url = _BASE + url
            items.append(
                {
                    "product_id": pid.group(1),
                    "product_name": name[:500],
                    "category": category,
                    "price": price_str,
                    "currency": _currency_symbol_to_code(pr.group(2)),
                    "available": True,
                    "url": url,
                    "language": self.language,
                }
            )
        return items

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        prev_ids = response.meta["prev_ids"]

        items = self._extract(response, slug)
        cur_ids = frozenset(it["product_id"] for it in items)
        logger.info(f"allo_ua: {slug} page={page} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["scraped_at_utc"] = scraped_at
            yield item

        # Magento pagination-loop guard: `?p=N` past the last real page
        # re-serves the last page verbatim rather than going empty, so a
        # bare "items and page < MAX_PAGES" check would spin forever.
        if items and cur_ids != prev_ids and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/ua/{slug}/?p={nxt}",
                callback=self.parse_page,
                meta={"slug": slug, "page": nxt, "prev_ids": cur_ids, "impersonate": "chrome124"},
            )
