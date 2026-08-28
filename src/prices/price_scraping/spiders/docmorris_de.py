"""
Spider for DocMorris Germany — https://www.docmorris.de/ (online pharmacy).

Next.js SSR storefront backed by an Algolia index named
`pro_docmorris_products`. The homepage/category shell embeds the first
Algolia results page inside a standard `<script id="__NEXT_DATA__">` blob at
`props.pageProps.serverState.initialResults.pro_docmorris_products.results[0]`
— a plain JSON object, no devalue/RSC indirection.

Enumerability proved live 2026-08-17 on a real category (not the homepage):
`/arzneimittel-gesundheit/schmerzmittel` returns `page: 0` with no query
param and `page: 1` (zero product-id overlap with page 0's 28 hits) with
`?page=2` — the site's pagination is 1-indexed in the URL, 0-indexed in the
response. Guessed subcategory slugs (`/beauty-pflege/gesichtspflege` etc.)
404 — there is no `children` field on the category payload to discover them
safely — so this spider instead walks the five confirmed top-level
department paths directly (each department root itself returns a live,
paginated Algolia result set: 42k-68k hits, `nbPages` capped at 36 by the
Algolia UI regardless of true hit count).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

_DEPARTMENTS = [
    "arzneimittel-gesundheit",
    "beauty-pflege",
    "vitamine-sport-ernaehrung",
    "kinder-familie",
    "tiergesundheit-tierbedarf",
]
MAX_PAGES = 20


class DocmorrisDeSpider(scrapy.Spider):
    name = "docmorris_de"
    allowed_domains = ["docmorris.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        for dept in _DEPARTMENTS:
            yield scrapy.Request(
                f"https://www.docmorris.de/{dept}",
                callback=self.parse_department,
                meta={"impersonate": self.IMPERSONATE_PROFILE, "dept": dept, "page": 1},
            )

    def parse_department(self, response):
        dept = response.meta["dept"]
        page = response.meta["page"]

        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.info(f"{self.name}: no __NEXT_DATA__ at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.info(f"{self.name}: unparseable __NEXT_DATA__ at {response.url}")
            return

        pp = (data.get("props") or {}).get("pageProps") or {}
        ir = (pp.get("serverState") or {}).get("initialResults") or {}
        block = ir.get("pro_docmorris_products") or {}
        results = block.get("results") or []
        if not results:
            logger.info(f"{self.name}: no Algolia results at {response.url}")
            return
        res0 = results[0]
        hits = res0.get("hits") or []
        n_pages = res0.get("nbPages") or 1
        logger.info(
            f"{self.name}: {dept} page={page} hits={len(hits)} nbPages={n_pages}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for hit in hits:
            name = hit.get("name")
            price = (hit.get("pricing") or {}).get("price")
            product_id = hit.get("readable_id")
            slug = hit.get("slug")
            if not (name and price is not None and product_id):
                continue
            category = None
            hierarchy = hit.get("category_hierarchy") or {}
            lv0 = hierarchy.get("lv0")
            if lv0:
                category = lv0[0]
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": bool(hit.get("has_stock")),
                "url": f"https://www.docmorris.de/{dept}/{slug}/{product_id}"
                if slug
                else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if page < min(n_pages, MAX_PAGES):
            yield scrapy.Request(
                f"https://www.docmorris.de/{dept}?page={page + 1}",
                callback=self.parse_department,
                meta={
                    "impersonate": self.IMPERSONATE_PROFILE,
                    "dept": dept,
                    "page": page + 1,
                },
            )
