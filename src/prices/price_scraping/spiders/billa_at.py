"""
Spider for BILLA Online Shop (Austria) -- https://shop.billa.at/.

Nuxt-rendered storefront (distinct build from billa_cz/billa_sk -- same
REWE-family "ws-*" component naming but a different category-URL shape:
/kategorie/<slug>-<id> here vs /produkty/<slug> in CZ). Server-rendered
category listing pages carry full product tiles with no JS execution
needed; verified live 2026-09-06.

584 leaf category slugs harvested from https://shop.billa.at/sitemap.xml
(only that sitemap carries the full leaf-category list -- the homepage
nav exposes just 4 of them) -- listed in `_billa_at_categories.txt`.

Pagination is INCREMENTAL and clean (unlike billa_cz's cumulative SSR
quirk): `/kategorie/<slug>?page=N` returns a disjoint 30-product page each
time (verified live: page=1 and page=2 on obst-und-gemuese-13751 share
zero product slugs). Walk page=1,2,3... and stop once a page returns
fewer than 30 tiles (last page) or 0 tiles (page beyond the end).

Each product tile (`li[data-test="product-tile"]`) carries
`data-product-slug` and `data-teaser-name`. The full decimal price lives
in a screen-reader-only span inside the price block
(`span.d-sr-only` with text like "2,39 €") -- more reliable than the
visually-split main/superscript digits, which are two separate DOM nodes
("2" + "39 €").

Confirmed live 2026-09-06: /kategorie/obst-und-gemuese-13751 -> 200, 295
products across 10 pages, e.g. "Ja! Natürlich Bananen" (ja-natuerlich-
bananen-00402489) EUR 2.39.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://shop.billa.at"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_billa_at_categories.txt"
_MAX_PAGES = 40  # safety cap per category
_PAGE_SIZE = 30
_PRICE_RE = re.compile(r"([0-9]+,[0-9]{2})\s*€")


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class BillaAtSpider(scrapy.Spider):
    name = "billa_at"
    allowed_domains = ["billa.at"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/kategorie/{slug}?page=1",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()

        tiles = response.css('li[data-test="product-tile"]')
        count = len(tiles)
        logger.info(f"billa_at: {slug} page={page} count={count}")

        for tile in tiles:
            product_slug = tile.attrib.get("data-product-slug")
            name = tile.attrib.get("data-teaser-name")
            price_text = tile.css("span.d-sr-only::text").get()
            if not product_slug or not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            yield {
                "product_id": product_slug,
                "product_name": name.strip()[:500],
                "category": slug,
                "price": m.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/produkte/{product_slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if count == _PAGE_SIZE and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/kategorie/{slug}?page={nxt}",
                callback=self.parse_page,
                meta={"slug": slug, "page": nxt},
            )
