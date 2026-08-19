"""
Spider for Billa CZ (Czech Republic) — https://www.billa.cz/.

Nuxt/React hybrid storefront that server-renders its full product catalog
under /produkty/<slug>-<id>. The category listing at /produkty exposes 18
top-level category slugs covering the whole assortment (dairy, meat, fruit
& veg, frozen, drinks, household, cosmetics, tobacco, ...); slugs are listed
in `_billa_cz_categories.txt`.

Pagination is cumulative, not incremental: /produkty/<slug>?page=N
server-renders ALL items from page 1..N in one response (e.g. page=1 -> 30
items, page=5 -> 150 items, plateauing once the category is exhausted; a
page beyond the last valid one renders 0 items). So we walk page=1,2,3...
and stop as soon as a page's item count does not exceed the previous page's
count, then emit the previous (maximal) page's full item list.

Each product tile (`li[data-test="product-tile"]`) carries
`data-product-slug`, `data-teaser-name`, and a nested
`span.ws-product-price-value__main` with the price text (e.g. '34,90 Kč').

Re-verified live 2026-08-06: /produkty/ovoce-a-zelenina-1165 -> 200, growth
30/60/90...355 items plateauing at page=16 (page=17 -> 0). Real product
'Banán' 39,90 Kč.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.billa.cz"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_billa_cz_categories.txt"
_MAX_PAGES = 40  # safety cap per category
_PRICE_RE = re.compile(r"([0-9]+,[0-9]{2})")


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class BillaCzSpider(scrapy.Spider):
    name = "billa_cz"
    allowed_domains = ["billa.cz"]
    currency = "CZK"
    language = "cs"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/produkty/{slug}?page=1",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1, "prev_items": [], "prev_count": 0},
            )

    def _extract(self, response, category: str):
        items = []
        for tile in response.css('li[data-test="product-tile"]'):
            slug = tile.attrib.get("data-product-slug")
            name = tile.attrib.get("data-teaser-name")
            price_text = tile.css("span.ws-product-price-value__main::text").get()
            if not slug or not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            items.append(
                {
                    "product_id": slug,
                    "product_name": html.unescape(name).strip()[:500],
                    "category": category,
                    "price": m.group(1).replace(",", "."),
                    "currency": self.currency,
                    "available": True,
                    "url": f"{_BASE}/produkt/{slug}",
                    "language": self.language,
                }
            )
        return items

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        prev_items = response.meta["prev_items"]
        prev_count = response.meta["prev_count"]

        items = self._extract(response, slug)
        count = len(items)
        logger.info(f"billa_cz: {slug} page={page} count={count}")

        if count <= prev_count:
            yield from self._emit(prev_items)
            return

        if page >= _MAX_PAGES:
            yield from self._emit(items)
            return

        nxt = page + 1
        yield scrapy.Request(
            f"{_BASE}/produkty/{slug}?page={nxt}",
            callback=self.parse_page,
            meta={"slug": slug, "page": nxt, "prev_items": items, "prev_count": count},
        )

    def _emit(self, items):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for item in items:
            item["scraped_at_utc"] = scraped_at
            yield item
