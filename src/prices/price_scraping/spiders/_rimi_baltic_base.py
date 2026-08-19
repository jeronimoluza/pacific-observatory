"""
Shared base for the three Rimi Baltic storefronts (Estonia / Latvia /
Lithuania) — same corporate platform, one per-country domain each.

No category-browse API or working ?start=N grid pagination was found on
any of the three sites (homepages and guessed category slugs render empty
0,00-price placeholders pre-JS). But the site-search endpoint is fully
SSR and paginates cleanly: GET .../<search-path>?query=<term>&currentPage=N
returns a page of `data-gtm-eec-product='{"id":...,"name":...,"price":...,
"currency":...}'` JSON blocks per hit — confirmed live 2026-08-06 on all
three domains (40 hits/page, currentPage links up to 30 present in the
response for a common term). Coverage here is a keyword-search sweep
across common grocery nouns in the local language, not a full category
walk, since no browse API was found — narrower than a category tree but
every row is a real priced SKU.
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

_PRODUCT_RE = re.compile(r"data-gtm-eec-product='([^']+)'")
_MAX_PAGES_PER_TERM = 3


class RimiBalticBaseSpider(scrapy.Spider):
    allowed_domains: list[str] = []
    currency = "EUR"
    language = "en"
    SEARCH_URL: str = ""  # e.g. "https://www.rimi.lv/e-veikals/lv/meklesana"
    SEARCH_TERMS: list[str] = []

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _request(self, term: str, page: int):
        return scrapy.Request(
            f"{self.SEARCH_URL}?query={term}&currentPage={page}",
            callback=self.parse_page,
            meta={"term": term, "page": page},
        )

    async def start(self):
        for term in self.SEARCH_TERMS:
            yield self._request(term, 1)

    def parse_page(self, response):
        term = response.meta["term"]
        page = response.meta["page"]
        blocks = _PRODUCT_RE.findall(response.text)
        if not blocks:
            return
        for raw in blocks:
            item = self._item(html.unescape(raw))
            if item:
                yield item
        if page < _MAX_PAGES_PER_TERM and len(blocks) >= 20:
            yield self._request(term, page + 1)

    def _item(self, raw_json: str):
        try:
            data = json.loads(raw_json)
        except ValueError:
            return None
        name = (data.get("name") or "").strip()
        price = data.get("price")
        pid = str(data.get("id") or "")
        if not name or price is None or not pid:
            return None
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": data.get("category") or None,
            "price": str(price),
            "currency": data.get("currency") or self.currency,
            "available": True,
            "url": f"{self.SEARCH_URL}#product-{pid}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Live scrape
    # (parse_page/_item, above) reads the same `data-gtm-eec-product='{...}'`
    # JSON block this reuses -- but that block turns out to be embedded on
    # EVERY Rimi page type Common Crawl archives, not just search-result
    # pages: homepage, category listing, and individual product-detail pages
    # all carry it (confirmed live across all 3 domains: rimi.ee 8/8, rimi.lv
    # 8/8, rimi.lt 7/8 archived samples had >=1 block; the one miss was a
    # category page whose certificate filter matched zero products). That
    # makes it a far better primary tier here than the shared schema.org
    # tier, which only fires on PDP pages (`/p/<id>`) and even then not
    # always (some PDP JSON-LD omits `offers`) -- the shared tiers are kept
    # as a fallback for the rare page with no GTM block at all.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Rimi Baltic page (any page type).

        Pure/stateless: no Scrapy Response, no network, no class state.
        Yields 0 or more rows. Does NOT stamp `scraped_at_utc` -- the
        backfiller stamps the snapshot time itself.
        """
        yielded = False
        for raw in _PRODUCT_RE.findall(html_text):
            item = cls._archived_item(html.unescape(raw), url)
            if item:
                yielded = True
                yield item
        if yielded:
            return

        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        for row in rows:
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row

    @classmethod
    def _archived_item(cls, raw_json: str, page_url: str) -> dict | None:
        try:
            data = json.loads(raw_json)
        except ValueError:
            return None
        name = (data.get("name") or "").strip()
        price = data.get("price")
        pid = str(data.get("id") or "")
        if not name or price is None or not pid:
            return None
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": data.get("category") or None,
            "price": str(price),
            "currency": data.get("currency") or cls.currency,
            "available": True,
            "url": page_url,
            "language": cls.language,
        }
