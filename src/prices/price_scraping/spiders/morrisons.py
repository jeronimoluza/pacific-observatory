"""Spider for Morrisons (United Kingdom) -- https://groceries.morrisons.com/.

Morrisons is one of the UK "big four" supermarket chains. Discovery lead
(wave 4, bare hostname `morrisons.com`, triage Verdict "SUSPECT",
AI_NOTES: "Major national chain on an enterprise stack behind a CDN/WAF...
Treat as a last-resort build"). That triage read turned out to be wrong on
re-probe 2026-09-06: category pages are plain server-rendered HTML with
real prices, reachable via `curl_cffi impersonate=chrome124` with **no
postcode/store selection required** -- unlike Tesco, Waitrose, ASDA and
Ocado (all confirmed BLOCKED in the same wave), which all gate their
catalogue behind a delivery address or a genuine WAF challenge.

The homepage does load an AWS WAF captcha SDK script
(`captcha-sdk.awswaf.com`) defensively, but it was never triggered on any
of the ~10 plain GET requests made during probing/testing -- the WAF
appears to challenge on behavioural signals, not on a bare browser-TLS GET.

**Category discovery**: the homepage embeds the *entire* category tree as
JSON in `window.__INITIAL_STATE__.data.categories.categories` (keyed by
UUID, each entry carrying `fullURLPath` and a numeric `retailerId`). The
live category URL is `/categories/<fullURLPath.lower()>/<retailerId>`
(confirmed against `Events-Inspiration-Ways-To-Save/Market-Street` ->
`/categories/events-inspiration-ways-to-save/market-street/184295`, the one
category URL that also appears as a literal `<a>` on the homepage). 226 leaf
categories (`children: []`) were extracted this way and hardcoded into
`_CATEGORIES_FILE` -- the spider does not need to re-parse the homepage at
runtime.

**Selectors**: each product tile is delimited by `data-test="fop-body"`
(50 occurrences per page = 50 tiles); within a tile, the PDP link is
`href="/products/<slug>/<numeric-id>"`, the name is
`data-test="fop-title">NAME<`, and the price is `data-test="fop-price">
£D.DD`. No pagination endpoint was found on sampled categories (no
`page=`/`p=` query honoured, no pager markup) -- categories appear to
render their full assortment (up to 50 items) on one page; breadth comes
from the 226-category walk.

Page family parsed: category listing pages only (name + price both come
from the grid; PDP never fetched).

Test run 2026-09-06 (--max-items 10): passed, real GBP prices (e.g.
£0.78-£13.33), 0 blank names, matches the rendered page.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://groceries.morrisons.com"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_morrisons_categories.txt"

_BLOCK_SPLIT_RE = re.compile(r'(?=data-test="fop-body")')
_HREF_RE = re.compile(r'href="(/products/[^"]+/(\d+))"')
_TITLE_RE = re.compile(r'data-test="fop-title">([^<]+)<')
_PRICE_RE = re.compile(r'data-test="fop-price">£([0-9]+\.[0-9]{2})')


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class MorrisonsSpider(scrapy.Spider):
    name = "morrisons"
    allowed_domains = ["groceries.morrisons.com"]
    currency = "GBP"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
        "DOWNLOAD_TIMEOUT": 45,
        "RETRY_TIMES": 3,
    }

    def start_requests(self):
        for path in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/categories/{path}",
                callback=self.parse_category,
                meta={"path": path, "impersonate": "chrome124"},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        category_name = path.rsplit("/", 1)[0].replace("-", " ")
        yielded = 0
        for block in _BLOCK_SPLIT_RE.split(response.text)[1:]:
            href_m = _HREF_RE.search(block)
            title_m = _TITLE_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not (href_m and title_m and price_m):
                continue
            try:
                price_val = float(price_m.group(1))
            except ValueError:
                continue
            if price_val <= 0:
                continue
            name = title_m.group(1).strip()
            if not name:
                continue

            yield {
                "product_id": href_m.group(2),
                "product_name": name,
                "price": price_val,
                "currency": self.currency,
                "category": category_name,
                "url": _BASE + href_m.group(1),
                "language": self.language,
                "scraped_at_utc": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1

        logger.info(f"morrisons: {path} yielded={yielded}")
