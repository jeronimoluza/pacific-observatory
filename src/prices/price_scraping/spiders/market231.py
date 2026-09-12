"""Market231 -- https://market231.com/

"Liberia's Trusted Online Marketplace", a Monrovia-run classifieds/marketplace
platform (React CRA front end, emergent.sh backend). Categories span vehicles,
phones and electronics, home and furniture, appliances, fashion and services.

Probed live 2026-09-12: the HTML is an empty SPA shell (10 KB, zero prices),
but the bundle at /static/js/main.*.js references a completely open,
unauthenticated REST endpoint -- `Playwright to discover, plain HTTP to
scrape`:

    GET /api/listings?limit=100&skip=N   ->  application/json, list of rows

PAGINATION TRAP, measured the hard way on 2026-09-12 -- write this one down.
Default limit is 20 and `?limit=200` is clamped to 100. Of the four paging
params that LOOK like they work, three silently re-serve page one:

    ?offset=N   200, returns 100 rows -- but the SAME 100 rows for every N.
                A first probe at offset=0/100/200 all returned "100 rows",
                which reads exactly like working pagination. It is not: the
                id sets are identical. A first run of this spider walked
                offset to 19,900, logged "rows=100" 200 times, and scraped
                exactly 100 items because the DuplicationPipeline dropped
                every repeat.
    ?page=N     ignored (20 rows, full overlap with page one)
    ?start=N    ignored (20 rows, full overlap)
    ?cursor=N   ignored (20 rows, full overlap)
    ?skip=N     WORKS -- zero overlap with page one.

So: page on `skip`, and never trust a row COUNT as evidence that a page
advanced. This spider additionally stops if a page's id set is one it has
already seen, so the same trap cannot cost another run.

Catalog size measured via skip: 100 + 35 = 135 active listings.

Row shape (live sample):
    {"title": "iPhone", "price": 190.0, "price_lrd": 33637.6,
     "currency_entered": "USD", "category": "phones-electronics",
     "county": "Montserrado", "slug": "iphone-phones-electronics-...",
     "status": "active", "listing_type": "sale"}

CURRENCY: taken per row from the listing's own `currency_entered`, because
this really is a dual-currency board -- sellers post in either USD or LRD and
the API carries both `price` (as entered) and a converted `price_lrd`. We emit
the as-entered price with its as-entered currency and never the converted
field, so no synthetic FX enters the corpus. `currency` on the class is the
fallback only.

channel: marketplace -- seller-authored listings, which is exactly the
population `enrich/census.py` excludes from the corpus census. Tagged honestly
rather than dressed up as dept-store.

Page family parsed: API (/api/listings). The `url` emitted is the human
permalink built from the row slug; the spider never fetches it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import scrapy

_BASE = "https://market231.com"
_PAGE = 100
_MAX_SKIP = 20000  # safety stop


class Market231Spider(scrapy.Spider):
    name = "market231"
    allowed_domains = ["market231.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
        "ROBOTSTXT_OBEY": False,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_ids: set = set()

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/api/listings?limit={_PAGE}&skip=0",
            callback=self.parse_page,
            meta={"skip": 0},
        )

    def parse_page(self, response):
        try:
            rows = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.warning(f"{self.name}: non-JSON at {response.url}")
            return
        if not isinstance(rows, list):
            return
        skip = response.meta["skip"]
        page_ids = {r.get("id") for r in rows}
        fresh = page_ids - self._seen_ids
        self._seen_ids |= page_ids
        self.logger.info(
            f"{self.name}: skip={skip} rows={len(rows)} new_ids={len(fresh)}"
        )
        if not fresh:
            # the endpoint re-served a page we already have -- stop rather
            # than let the dupe filter quietly absorb it (see the module
            # docstring; this is how the `offset` trap was found)
            return

        for row in rows:
            if row.get("status") not in (None, "active"):
                continue
            price = row.get("price")
            name = (row.get("title") or "").strip()
            if not name or price in (None, "", 0):
                continue
            try:
                if float(price) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            slug = row.get("slug")
            yield {
                "product_id": row.get("id"),
                "product_name": name[:500],
                "price": str(price),
                "currency": row.get("currency_entered") or self.currency,
                "category": row.get("category"),
                "url": f"{_BASE}/listing/{slug}" if slug else _BASE,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }

        if len(rows) == _PAGE and skip + _PAGE < _MAX_SKIP:
            nxt = skip + _PAGE
            yield scrapy.Request(
                f"{_BASE}/api/listings?limit={_PAGE}&skip={nxt}",
                callback=self.parse_page,
                meta={"skip": nxt},
            )
