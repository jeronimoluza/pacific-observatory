"""Spider for Spesa Online COAL (San Marino) --
https://spesa.gruppoce.sm/.

The storefront is a Next.js static-export shell with no data at build time
(`__NEXT_DATA__.props.pageProps` is empty) -- product data is fetched
client-side from a same-brand SaaS backend on a different domain, found via
a Playwright network trace (not visible as a literal string in any of the
Next.js JS chunks): `spesa.lenny.sm` ("Lenny", a white-label Italian grocery
e-commerce platform used by COAL, the San Marino retail/consumer
cooperative group -- see the `store/partners` endpoint, which lists "Coal"
among the brands served).

Two open (no-auth) endpoints confirmed live 2026-09-01:
- `GET /api/category/tree` -- full category tree, 22 top-level nodes / 210
  leaves, each leaf carrying a `count` of products.
- `GET /api/product/search?category_id=<id>&page=<n>` -- 20 products/page,
  1-indexed, real pagination confirmed (page 1 vs page 2 on category 479
  "Acqua" returned disjoint product-slug sets); stops when a page returns
  an empty list.

Products can appear under more than one leaf category (breadcrumb-style
tagging), so results are deduped globally on `slug`. Price: prefer
`discounted_price` when present (the on-sale price), else `unit_price`;
rows with a null/zero price are dropped, not shipped. PDP URL
(`https://spesa.gruppoce.sm/product/<slug>`) independently re-verified
live to 200 and render the same product.

**Confirmed API defect, worked around here, NOT in a shared base (this
spider is a one-off, nothing else depends on it):** `category_id` is not
validated server-side once a category's real content is exhausted -- it
silently falls back to serving an unrelated, unbounded default listing
(observed live: `category_id=818`, tree-declared `count: 3`, kept
returning 20-row pages of wine products identical to `category_id=479`'s
listing, all the way past page 3). The tree's `count` field cannot be
trusted as a hard pagination bound either. Pagination therefore stops on
the first page that contributes **zero NEW (post-dedup) items**, not on
the first empty array -- an empty-array-only stop would run every small
category out to `MAX_PAGES` against the fallback stream. The tradeoff:
a category whose own genuine content is fully shadowed by an
earlier-processed sibling on page 1 stops after one page, which only
loses re-fetching of items already captured elsewhere, never real
coverage.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_BASE = "https://spesa.lenny.sm/api"
_TREE_URL = f"{_API_BASE}/category/tree"
_SEARCH_URL = f"{_API_BASE}/product/search"
_PDP_BASE = "https://spesa.gruppoce.sm/product"


class CoalSmSpider(scrapy.Spider):
    name = "coal_sm"
    allowed_domains = ["lenny.sm", "gruppoce.sm"]
    currency = "EUR"
    language = "it"
    # Raised from 200 by the orchestrator 2026-09-01. Two independent
    # unbounded runs both stopped at EXACTLY 4,000 rows (200 pages x 20
    # items) -- a reproducible round number is a cap signature, not a
    # catalog size. Because the backend's exhausted-category fallback
    # keeps serving real store products, the global _seen_slugs dedup
    # never fires an empty page, so MAX_PAGES was the only thing ending
    # the crawl. All 4,000 rows were distinct, so nothing collected was
    # wrong -- the catalog was simply cut off mid-stream.
    MAX_PAGES = 2000

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://spesa.gruppoce.sm/",
            "Origin": "https://spesa.gruppoce.sm",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_slugs: set[str] = set()

    async def start(self):
        yield scrapy.Request(_TREE_URL, callback=self.parse_tree)

    def parse_tree(self, response):
        try:
            tree = response.json()
        except ValueError:
            logger.warning(f"{self.name}: category tree not JSON")
            return

        leaf_ids: list[int] = []
        for cat in tree:
            subs = cat.get("subcategories") or []
            if subs:
                leaf_ids.extend(s["id"] for s in subs if s.get("id") is not None)
            elif cat.get("id") is not None:
                leaf_ids.append(cat["id"])

        leaf_ids = sorted(set(leaf_ids))
        logger.info(f"{self.name}: {len(tree)} top categories, {len(leaf_ids)} leaves")
        for cat_id in leaf_ids:
            url = f"{_SEARCH_URL}?category_id={cat_id}&page=1"
            yield scrapy.Request(
                url,
                callback=self.parse_search,
                meta={"cat_id": cat_id, "page": 1},
            )

    def parse_search(self, response):
        try:
            rows = response.json()
        except ValueError:
            return
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for row in rows:
            item = self._item(row, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(
            f"{self.name}: category={cat_id} page={page} rows={len(rows)} items={n}"
        )

        # Stop on zero NEW items, not on an empty array -- see the module
        # docstring's "Confirmed API defect" note. An exhausted/small
        # category_id falls back to an unrelated, never-empty default
        # listing rather than returning [].
        if n and page < self.MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_SEARCH_URL}?category_id={cat_id}&page={nxt}",
                callback=self.parse_search,
                meta={"cat_id": cat_id, "page": nxt},
            )

    def _item(self, row, scraped_at):
        slug = row.get("slug")
        name = row.get("name")
        if not slug or not name:
            return None
        if slug in self._seen_slugs:
            return None
        self._seen_slugs.add(slug)

        price = row.get("discounted_price")
        if price is None:
            price = row.get("unit_price")
        if not price or price <= 0:
            return None

        cats = row.get("categories") or []
        category = cats[0].get("name") if cats else None

        return {
            "product_id": slug,
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(row.get("enabled", True))
            and not row.get("deleted_timestamp"),
            "url": f"{_PDP_BASE}/{slug}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
