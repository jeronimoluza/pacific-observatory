"""Spider for Silpo (Ukraine) -- https://silpo.ua/.

Silpo is Ukraine's largest modern supermarket chain. `silpo.ua` (city
defaults to Kyiv when no city cookie is set) is a Nuxt SSR storefront --
curl_cffi impersonate=chrome124 clears cleanly with HTTP 200 (bare curl
403s; re-probed 2026-09-01 after `known_blockers.md`'s 2026-06-09 "wartime
cohort" entry recorded a 403 from a non-UA IP -- chrome124 impersonation was
the fix, not a UA-resident IP).

The category page HTML embeds the full Nuxt payload cache inline, which
includes the raw JSON response from the internal
`sf-ecom-api.silpo.ua/v1/.../products` endpoint (a page-scoped object
literal `{"limit":47,"offset":0,"total":N,"items":[{...}, ...]}`). Calling
that API directly 404s without the right request shape (POST body params
reverse-engineered unsuccessfully in probing) -- but the SSR HTML always
carries it, so this spider regexes it out of the page source rather than
calling the API. `_extract_item_arrays` finds `"items":[` and does a
bracket-depth walk (string/escape aware) to isolate the matching JSON array,
then `json.loads`s it directly -- far more robust than trying to regex
individual product objects out of arbitrarily-nested promotion sub-arrays.

Each item carries: `externalProductId` (stable numeric id), `title`,
`displayPrice` (current shelf price, UAH implicit -- Silpo is UAH-only),
`slug` (-> PDP url `/product/<slug>`), `sectionSlug` (leaf category),
`stock` (> 0 => available). The embedded payload appears twice per page
(SSR render + hydration cache) -- duplicate `externalProductId`s are
expected and are deduped downstream by the DuplicationPipeline on `url`.

Pagination is `?page=N`, incremental (disjoint slices) -- verified live
2026-09-01: /category/chai-5126 page=1 -> 47 unique externalProductIds,
page=2 -> 47 unique ids, only 1 id overlapping (a promoted/pinned SKU).
Walk stops when a page yields 0 items.

The 259 category slugs (`_silpo_ua_categories.txt`) are the full mega-menu
list scraped from the homepage / any category page -- both parent hubs
(e.g. `kava-chai-359`) and leaves (e.g. `chai-5126`) are included; hub pages
that carry no direct product grid simply yield 0 items and the walk moves
on, costing one extra request each.

Kyiv catalogue (Ukrainian convention for city-priced sources, no city
selector needed -- Kyiv is the unauthenticated default).
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://silpo.ua"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_silpo_ua_categories.txt"
_MAX_PAGES = (
    15  # safety cap per category; keeps the crawl breadth-first across 259 categories
)

_ITEMS_KEY_RE = re.compile(r'"items":\[')


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


def _extract_item_arrays(body: str) -> list[list[dict]]:
    """Bracket-depth walk from each `"items":[` to its matching `]`, then json.loads."""
    out = []
    for m in _ITEMS_KEY_RE.finditer(body):
        start = m.end() - 1  # position of the opening '['
        depth = 0
        in_str = False
        esc = False
        i = start
        n = len(body)
        while i < n:
            c = body[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
            i += 1
        arr_text = body[start:i]
        try:
            arr = json.loads(arr_text)
        except ValueError:
            continue
        if arr and isinstance(arr[0], dict) and "externalProductId" in arr[0]:
            out.append(arr)
    return out


class SilpoUaSpider(scrapy.Spider):
    name = "silpo_ua"
    allowed_domains = ["silpo.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/category/{slug}?page=1",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1, "impersonate": "chrome124"},
            )

    def _extract(self, response, category: str) -> list[dict]:
        items = {}
        for arr in _extract_item_arrays(response.text):
            for entry in arr:
                pid = entry.get("externalProductId")
                title = entry.get("title")
                slug = entry.get("slug")
                price = entry.get("displayPrice", entry.get("price"))
                if pid is None or not title or not slug or price is None:
                    continue
                name = html.unescape(str(title)).strip()
                name = re.sub(r"\s+", " ", name)
                if not name:
                    continue
                items[pid] = {
                    "product_id": str(pid),
                    "product_name": name[:500],
                    "category": entry.get("sectionSlug") or category,
                    "price": str(price),
                    "currency": self.currency,
                    "available": bool(entry.get("stock", 0))
                    and entry.get("stock", 0) > 0,
                    "url": f"{_BASE}/product/{slug}",
                    "language": self.language,
                }
        return list(items.values())

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        items = self._extract(response, slug)
        logger.info(f"silpo_ua: {slug} page={page} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["scraped_at_utc"] = scraped_at
            yield item

        if items and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/category/{slug}?page={nxt}",
                callback=self.parse_page,
                meta={"slug": slug, "page": nxt, "impersonate": "chrome124"},
            )
