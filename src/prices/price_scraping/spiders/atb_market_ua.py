"""Spider for ATB-Market (Ukraine) -- https://atbmarket.com/.

ATB is Ukraine's largest discount grocery chain by store count. The online
storefront (`atbmarket.com`, city defaults to Kyiv when no city cookie is
set) is a server-rendered, non-SPA site -- curl_cffi impersonate=chrome124
clears cleanly with HTTP 200 (bare curl 403s; re-probed 2026-09-01 after
`known_blockers.md`'s 2026-06-09 "wartime cohort" entry recorded a 403 from
a non-UA IP -- chrome124 impersonation was the fix, not a UA-resident IP).

Category listing at `/catalog/<id>-<slug>` embeds product cards directly in
the HTML (no JSON API, no Playwright needed) -- one `<article class=
"catalog-item ...">` per product, carrying `data-productid`, a
`catalog-item__title` anchor (name + PDP url), and a `<data value="XX.XX"
class="product-price__top">` price node with a sibling `data-currency="UAH"`
attribute on the add-to-cart widget.

Pagination is `?page=N`, incremental (each page is a disjoint slice, not
cumulative) -- verified live 2026-09-01: /catalog/318-chay page=1 -> 36
distinct product ids, page=2 -> 36 distinct ids, ZERO overlap. Walk stops
when a page yields 0 items.

The 151 category paths (`_atb_market_ua_categories.txt`) are the full
mega-menu extracted from the homepage / any catalog page -- the same 151
links appear site-wide, so no separate hub-discovery crawl is needed (unlike
rozetka_ua, whose top-level nav hubs are empty umbrellas). Both parent
categories (e.g. `285-bakaliya`) and their children (e.g. `312-tsukor`) list
products directly, so some products are reachable from more than one
category page -- the DuplicationPipeline's url-dedup drops the repeats
(same PDP url), so this does not double-count.

Kyiv catalogue (Ukrainian convention for city-priced sources, no city
selector cookie needed -- Kyiv is the unauthenticated default).
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://atbmarket.com"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_atb_market_ua_categories.txt"
_MAX_PAGES = (
    15  # safety cap per category; keeps the crawl breadth-first across 151 categories
)

_ARTICLE_SPLIT_RE = re.compile(r'(?=<article class="[^"]*catalog-item)')
_PRODUCT_ID_RE = re.compile(r'data-productid="(\d+)"')
_CURRENCY_RE = re.compile(r'data-currency="([A-Z]{3})"')
_NAME_URL_RE = re.compile(
    r'<div class="catalog-item__title[^"]*">\s*<a href="(/product/[^"]+)">([^<]+)</a>'
)
_PRICE_RE = re.compile(r'<data value="([0-9]+\.[0-9]+)" class="product-price__top">')


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class AtbMarketUaSpider(scrapy.Spider):
    name = "atb_market_ua"
    allowed_domains = ["atbmarket.com"]
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
                f"{_BASE}/catalog/{slug}?page=1",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1, "impersonate": "chrome124"},
            )

    def _extract(self, response, category: str) -> list[dict]:
        items = []
        for block in _ARTICLE_SPLIT_RE.split(response.text)[1:]:
            pid = _PRODUCT_ID_RE.search(block)
            nm = _NAME_URL_RE.search(block)
            pr = _PRICE_RE.search(block)
            if not (pid and nm and pr):
                continue
            cur = _CURRENCY_RE.search(block)
            name = html.unescape(nm.group(2)).strip()
            name = re.sub(r"\s+", " ", name)
            if not name:
                continue
            items.append(
                {
                    "product_id": pid.group(1),
                    "product_name": name[:500],
                    "category": category,
                    "price": pr.group(1),
                    "currency": (cur.group(1) if cur else self.currency),
                    "available": True,
                    "url": _BASE + nm.group(1),
                    "language": self.language,
                }
            )
        return items

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        items = self._extract(response, slug)
        logger.info(f"atb_market_ua: {slug} page={page} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["scraped_at_utc"] = scraped_at
            yield item

        if items and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/catalog/{slug}?page={nxt}",
                callback=self.parse_page,
                meta={"slug": slug, "page": nxt, "impersonate": "chrome124"},
            )
