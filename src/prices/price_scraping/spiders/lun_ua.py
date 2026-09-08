"""Spider for LUN (Ukraine) -- https://lun.ua/ -- residential rental listings.

LUN is Ukraine's largest real-estate listings aggregator. Discovery lead
(wave 3, bare hostname `lun.ua`). curl_cffi impersonate=chrome124 clears
with a clean HTTP 200, no UA-resident IP needed.

Server-rendered React (SSR, hashed CSS-module class names, e.g.
`RealtyCard-module-scss-module__tBtxOq__price` -- the hash segment is
build-specific, so selectors match on the stable `__price` / `__title`
suffix rather than the full class string). Listing cards carry:
  - a numeric internal id in a `data-event-options="...page_id:<id>|..."`
    attribute (no plain `<a href>` to the PDP -- navigation is
    client-side JS from a `<button>`, not a static anchor)
  - price text in `<div class="...__price">26 000 грн</div>` (negotiable
    listings show non-numeric text here, e.g. "Договірна", and are
    skipped when no digits are found)
  - address/title text in `<h3 class="...__title">Соломʼянська вулиця,
    38</h3>`

**PDP url reconstruction**: the card exposes no PDP link at all, so the
url is built from the `page_id` as `https://lun.ua/realty/<page_id>` --
verified live 2026-09-06 by cross-checking `lun.ua/realty/4721614878`'s
`<title>` and price text ("26 000 грн") against the exact listing sampled
from the search-results card carrying that same `page_id`.

Pagination is `?page=N`, 24 distinct listings/page -- enumerability
confirmed live 2026-09-06: `/rent/kyiv/flats` page 1 vs page 2 return
fully disjoint id sets (0 overlap). A page's JSON-LD block is aggregate
SEO markup only (`AggregateOffer` with `lowPrice`/`highPrice`/
`offerCount` for the whole collection) and carries no per-listing data or
urls -- same gotcha as olx_ro's JSON-LD block; do not use it.

Scoped to Kyiv long-term flat rentals (`/rent/kyiv/flats`) --
`coicop_codes: ["04.1.1"]` (residential rentals), narrow source,
short-circuits the classifier. `pricing_basis` is monthly, consistent
with the worked "residential rentals" example in the onboarding skill.

Page family parsed: listing only (the reconstructed `/realty/<id>` PDP
url is never fetched by the spider itself).

Test run 2026-09-06 (--max-items 60, closespider-timeout 120): passed,
distinct product_id per row, 0 blank names, 0 zero/negative prices, 100%
UAH.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://lun.ua"
_MAX_PAGES = 15

_BLOCK_SPLIT_RE = re.compile(r'(?=data-testid="realty-card-container")')
_PAGE_ID_RE = re.compile(r"page_id:(\d+)")
_PRICE_RE = re.compile(r'class="[^"]*__price">([^<]+)</div>')
_TITLE_RE = re.compile(r'<h3 class="[^"]*__title">([^<]+)</h3>')
_DIGITS_RE = re.compile(r"[\d\s]+")


class LunUaSpider(scrapy.Spider):
    name = "lun_ua"
    allowed_domains = ["lun.ua"]
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
        yield scrapy.Request(
            f"{_BASE}/rent/kyiv/flats?page=1",
            callback=self.parse_page,
            meta={"page": 1, "prev_ids": frozenset(), "impersonate": "chrome124"},
        )

    def _extract(self, response) -> list[dict]:
        items = []
        for block in _BLOCK_SPLIT_RE.split(response.text)[1:]:
            pid = _PAGE_ID_RE.search(block)
            pr = _PRICE_RE.search(block)
            nm = _TITLE_RE.search(block)
            if not (pid and pr and nm):
                continue
            price_match = _DIGITS_RE.search(pr.group(1))
            price_str = (price_match.group(0) if price_match else "").replace(" ", "").strip()
            if not price_str:
                continue  # negotiable ("Договірна") or otherwise non-numeric
            name = html.unescape(nm.group(1)).strip()
            name = re.sub(r"\s+", " ", name)
            if not name:
                continue
            items.append(
                {
                    "product_id": pid.group(1),
                    "product_name": name[:500],
                    "category": "rent/kyiv/flats",
                    "price": price_str,
                    "currency": self.currency,
                    "available": True,
                    "url": f"{_BASE}/realty/{pid.group(1)}",
                    "language": self.language,
                }
            )
        return items

    def parse_page(self, response):
        page = response.meta["page"]
        prev_ids = response.meta["prev_ids"]

        items = self._extract(response)
        cur_ids = frozenset(it["product_id"] for it in items)
        logger.info(f"lun_ua: page={page} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["scraped_at_utc"] = scraped_at
            yield item

        if items and cur_ids != prev_ids and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/rent/kyiv/flats?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt, "prev_ids": cur_ids, "impersonate": "chrome124"},
            )
