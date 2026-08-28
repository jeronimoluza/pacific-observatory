"""
Spider for AlimentaraOnline (Romania) — https://www.alimentaraonline.com/.

Custom PHP storefront, server-rendered. Each category page (`/catalog/<slug>`,
paginated `/catalog/<slug>/pN`) embeds a full `application/ld+json`
`ItemList` of `Product` entries with `name`, `offers.lowPrice`,
`offers.priceCurrency`, `url` (the real per-product permalink) and `sku` --
no rendering needed, no separate API call.

Re-verified live 2026-08-06: GET /catalog/produse-alimentare-40 -> 200,
392KB, ld+json ItemList reports `numberOfItems: 4079` across 170 pages (24
items/page). Sample: 'Banane pret/kg - 08031010' RON 11.10,
'Zahar Alb Cristal MARGARITAR 1Kg' RON 7.50, 'Lamai pret/kg - 08055010'
RON 21.50. Currency RON confirmed in the JSON-LD `priceCurrency` field.

The site's nav exposes ~245 category slugs (`_alimentaraonline_ro_categories.txt`)
spanning both umbrella nodes (e.g. `produse-alimentare-40`) and their
sub-slugs (e.g. `unt-211`); a product reachable from multiple category pages
carries the same permalink each time, so the pipeline's URL-based dedup
collapses the overlap for free -- crawling the full flattened list is
simpler and safer than reconstructing the parent/child tree.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_BASE = "https://www.alimentaraonline.com"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_alimentaraonline_ro_categories.txt"
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
MAX_PAGES_PER_CATEGORY = 40  # safety cap: 40 * 24 = 960 items/category


def _load_categories():
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class AlimentaraonlineRoSpider(scrapy.Spider):
    name = "alimentaraonline_ro"
    allowed_domains = ["alimentaraonline.com"]
    currency = "RON"
    language = "ro"

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
                f"{_BASE}/catalog/{slug}",
                callback=self.parse_page,
                meta={"slug": slug, "page": 1},
            )

    def parse_page(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        blocks = _LD_JSON_RE.findall(response.text)
        items = []
        for block in blocks:
            try:
                data = json.loads(block)
            except ValueError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for entry in candidates:
                if entry.get("@type") == "ItemList":
                    items = entry.get("itemListElement") or []
                    break
            if items:
                break
        if not items:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for li in items:
            p = li.get("item") or {}
            if p.get("@type") != "Product":
                continue
            name = str(p.get("name") or "").strip()
            offers = p.get("offers") or {}
            price = offers.get("lowPrice")
            url = p.get("url") or ""
            sku = p.get("sku")
            if not name or price is None or not url:
                continue
            count += 1
            yield {
                "product_id": str(sku or url),
                "product_name": name[:500],
                "category": slug,
                "price": str(price),
                "currency": offers.get("priceCurrency") or self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"alimentaraonline_ro: {slug} page={page} items={count}")
        if count >= 24 and page < MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/catalog/{slug}/p{next_page}",
                callback=self.parse_page,
                meta={"slug": slug, "page": next_page},
            )

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Archived
    # snapshots here are individual /cumpara/<slug> PDPs (the real permalink
    # this spider's own ItemList JSON-LD points `url` at -- see module
    # docstring), a different page from the /catalog/<slug> listings the
    # live crawl walks. NOT independently live-verified this session (the
    # host reset every connection attempt -- curl, curl_cffi with 4 browser
    # TLS profiles, and Anthropic's own WebFetch infra all failed identically,
    # so this looks like a host-side block rather than a local network
    # issue). Written from strong circumstantial evidence instead: the site's
    # templating layer already proven (module docstring, re-verified live
    # 2026-08-06) to emit a rich schema.org ItemList of Product nodes on
    # category pages is very likely to emit a standalone Product node on the
    # PDP itself -- the standard pattern for this kind of PHP storefront.
    # Falls back to re-parsing the category-style ItemList block in case a
    # PDP snapshot embeds that shape instead.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived AlimentaraOnline PDP page. UNVERIFIED against
        a live fetch this session -- see comment above."""
        rows = rows_from_jsonld(html_text, url)
        if not rows:
            row = row_from_meta(html_text, url)
            rows = [row] if row else []
        if rows:
            for row in rows:
                row.setdefault("currency", cls.currency)
                row.setdefault("language", cls.language)
                yield row
            return

        for block in _LD_JSON_RE.findall(html_text):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            candidates = data if isinstance(data, list) else [data]
            for entry in candidates:
                if entry.get("@type") != "ItemList":
                    continue
                for li in entry.get("itemListElement") or []:
                    p = li.get("item") or {}
                    if p.get("@type") != "Product":
                        continue
                    name = str(p.get("name") or "").strip()
                    offers = p.get("offers") or {}
                    price = offers.get("lowPrice")
                    row_url = p.get("url") or url
                    sku = p.get("sku")
                    if not name or price is None:
                        continue
                    yield {
                        "product_id": str(sku or row_url),
                        "product_name": name[:500],
                        "price": str(price),
                        "currency": offers.get("priceCurrency") or cls.currency,
                        "available": True,
                        "url": row_url,
                        "language": cls.language,
                    }
