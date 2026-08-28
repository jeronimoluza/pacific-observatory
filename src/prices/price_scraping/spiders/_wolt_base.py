"""
Shared base class for Wolt grocery-venue spiders (delivery marketplace).

Wolt's consumer web app (wolt.com) server-renders its React-Query cache into a
`<script type="application/json" class="query-state">` blob on every page —
both the plain venue page and each `.../items/<category-slug>` sub-page. No
JS execution is required; a plain `curl`/Scrapy GET returns the full blob.

Two-step walk per venue:
  1. GET the venue page -> the `venue-assortment/category-listing/<slug>/...`
     query gives every category slug for the store (item_ids are empty here,
     "partial" loading strategy).
  2. GET `.../venue/<slug>/items/<category-slug>` for each category -> the
     `venue-assortment/category/<slug>/<cat-slug>/...` query's first page
     carries up to 50 full item objects (name, price in minor units,
     unit_info, barcode_gtin). The site paginates further categories via a
     client-side `next_page_token` that is NOT reachable via a plain GET
     (SSR always renders page 1 regardless of a `?page=` query string) — this
     spider intentionally caps at page 1 per category. Large single
     categories (>50 SKUs) are undercounted; this is a known, accepted
     limitation, not a bug.

Subclasses set: name, allowed_domains=["wolt.com"], currency, language,
VENUE_PATH (e.g. "en/grc/athens"), VENUE_SLUG (e.g. "ab-vassilopoulos-mets").

Underscored filename — Scrapy's SpiderLoader skips classes without `name`.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_QUERY_STATE_RE = re.compile(
    r'<script type="application/json" class="query-state">(.*?)</script>',
    re.S,
)


def _extract_query_state(response_text: str) -> dict | None:
    m = _QUERY_STATE_RE.search(response_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


class WoltBaseSpider(scrapy.Spider):
    name = None
    allowed_domains = ["wolt.com"]
    currency: str = ""
    language: str = "en"
    VENUE_PATH: str = ""
    VENUE_SLUG: str = ""

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

    @property
    def venue_url(self) -> str:
        return f"https://wolt.com/{self.VENUE_PATH}/venue/{self.VENUE_SLUG}"

    async def start(self):
        yield scrapy.Request(self.venue_url, callback=self.parse_categories)

    def parse_categories(self, response):
        state = _extract_query_state(response.text)
        if not state:
            logger.warning(f"{self.name}: no query-state blob at {response.url}")
            return
        cat_slugs: list[str] = []
        for q in state.get("queries", []):
            qk = q.get("queryKey") or []
            if (
                len(qk) >= 3
                and qk[0] == "venue-assortment"
                and qk[1] == "category-listing"
                and qk[2] == self.VENUE_SLUG
            ):
                data = q.get("state", {}).get("data") or {}
                for cat in data.get("categories", []):
                    subcats = cat.get("subcategories") or []
                    if subcats:
                        # A parent with subcategories renders only its first
                        # leaf's items if requested directly -- walk every
                        # leaf subcategory slug instead.
                        for sub in subcats:
                            sub_slug = sub.get("slug")
                            if sub_slug:
                                cat_slugs.append(sub_slug)
                    else:
                        slug = cat.get("slug")
                        if slug:
                            cat_slugs.append(slug)
        logger.info(f"{self.name}: {len(cat_slugs)} categories")
        for slug in cat_slugs:
            yield scrapy.Request(
                f"{self.venue_url}/items/{slug}",
                callback=self.parse_category,
                meta={"category_slug": slug},
            )

    def parse_category(self, response):
        cat_slug = response.meta["category_slug"]
        state = _extract_query_state(response.text)
        if not state:
            logger.warning(f"{self.name}: no query-state blob at {response.url}")
            return
        items: list[dict] = []
        cat_name = cat_slug
        for q in state.get("queries", []):
            qk = q.get("queryKey") or []
            if len(qk) >= 2 and qk[0] == "venue-assortment" and qk[1] == "category":
                pages = (q.get("state", {}).get("data") or {}).get("pages") or []
                if pages:
                    cat_name = str(
                        (pages[0].get("category") or {}).get("name", cat_slug)
                    ).strip()
                    items = pages[0].get("items") or []
                break
        scraped_at = datetime.now(timezone.utc).isoformat()
        for it in items:
            name = it.get("name")
            price = it.get("price")
            if not name or price is None:
                continue
            unit_info = it.get("unit_info") or ""
            yield {
                "product_id": it.get("id"),
                "product_name": html.unescape(str(name)).strip()[:500],
                "category": cat_name,
                "price": round(price / 100, 2),
                "currency": self.currency,
                "available": True,
                "url": f"{self.venue_url}#{it.get('id')}",
                "language": self.language,
                "unit_info": unit_info,
                "barcode_gtin": it.get("barcode_gtin"),
                "scraped_at_utc": scraped_at,
            }

    @classmethod
    def parse_html(cls, html: str, url: str) -> Iterator[dict]:
        """Archived Wolt page -> price rows.

        Real archived Wolt URLs are NOT plain venue pages -- Common Crawl
        holds three page shapes under the declared `venue/` prefix: the bare
        venue root (category-listing only, no items), a category page
        (`.../venue/<slug>/items/<cat-slug>`), and an individual item page
        (`.../venue/<slug>/<item-name>-itemid-<hash>`). All three still
        server-render the same `<script class="query-state">` React-Query
        blob the live spider reads, so this replays that instead of the
        `__NEXT_DATA__` blob (grep found 0 occurrences across 24 sampled
        archived pages from 8 sources -- Wolt does not use it). Category and
        item queries share the live spider's item shape (name, price in
        minor units, unit_info, barcode_gtin); only the item-detail query
        lacks a category name. Root venue pages correctly yield nothing.

        Falls back to the shared JSON-LD/meta tiers first when present --
        rare here (1 of 24 sampled pages carried a schema.org Product node,
        an item-detail page) but free and occasionally the only surface
        available (query-state can be absent from very old snapshots).
        """
        rows = rows_from_jsonld(html, url)
        if rows:
            yield from rows
            return
        state = _extract_query_state(html)
        if state:
            seen_ids: set[str] = set()
            for row in cls._rows_from_query_state(state, url):
                item_id = row.get("product_id")
                if item_id:
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                yield row
            return
        meta_row = row_from_meta(html, url)
        if meta_row:
            yield meta_row

    @classmethod
    def _rows_from_query_state(cls, state: dict, url: str) -> Iterator[dict]:
        for q in state.get("queries", []):
            qk = q.get("queryKey") or []
            if len(qk) < 2 or qk[0] != "venue-assortment":
                continue
            data = (q.get("state") or {}).get("data") or {}
            if qk[1] == "category":
                for page in data.get("pages") or []:
                    cat_name = str(
                        (page.get("category") or {}).get("name") or ""
                    ).strip()
                    yield from cls._rows_from_items(
                        page.get("items") or [], cat_name or None, url
                    )
            elif qk[1] == "item":
                yield from cls._rows_from_items(data.get("items") or [], None, url)

    @classmethod
    def _rows_from_items(
        cls, items: list[dict], category: str | None, url: str
    ) -> Iterator[dict]:
        for it in items:
            name = it.get("name")
            price = it.get("price")
            if not name or price is None:
                continue
            row = {
                "product_id": it.get("id"),
                "product_name": html.unescape(str(name)).strip()[:500],
                "category": category,
                "price": str(round(price / 100, 2)),
                "currency": cls.currency,
                "available": True,
                "url": url,
            }
            unit_info = it.get("unit_info")
            if unit_info:
                row["unit_info"] = unit_info
            barcode = it.get("barcode_gtin")
            if barcode:
                row["barcode_gtin"] = barcode
            yield row
