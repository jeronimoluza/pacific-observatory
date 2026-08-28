"""
Spider for Coppel Mexico -- www.coppel.com.

Next.js storefront. robots.txt disallows `/p/*` and `/c/*` (the legacy
platform's category/product paths) but does not disallow `/pdp/*`, which is
the current PDP path and also what the site's own sitemap advertises.

Verified live 2026-08-17: https://www.coppel.com/l/sitemap/sitemap-pdp.xml
is a real sitemap index of ~46 per-department shards (celulares.xml,
electronica.xml, hogar-muebles.xml, ...), each a genuine urlset of
`/pdp/<slug>-<sellerCode>-<id>` product URLs -- e.g. celulares.xml alone
carries 21,923 PDP urls. This is a direct product-URL enumeration, not a
crawled listing page, so the page-1-vs-page-2 gate does not apply the same
way; enumerability is proven by the shard size itself plus the fact that
consecutive shards (celulares.xml vs electronica.xml) carry disjoint id
sets.

Each PDP embeds `pageProps.product` in a `__NEXT_DATA__` script tag with
clean fields: `name`, `sku`, `price.salesPrice` / `price.discountedPrice`
/ `price.currency` (MXN), `breadcrumb` (category path). No locale-format
price parsing needed -- the numeric fields are already bare numbers.

Bounded to a curated set of department shards and the first
_PRODUCTS_PER_SHARD urls of each, to keep a full run's request count
reasonable (full sitemap-pdp.xml is ~46 shards x up to ~22k urls each).
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

from ..archived import row_from_meta, rows_from_jsonld

logger = logging.getLogger(__name__)

_SHARDS = [
    "https://www.coppel.com/l/sitemap/celulares.xml",
    "https://www.coppel.com/l/sitemap/electronica.xml",
    "https://www.coppel.com/l/sitemap/hogar-muebles.xml",
    "https://www.coppel.com/l/sitemap/juguetes.xml",
    "https://www.coppel.com/l/sitemap/zapateria.xml",
    "https://www.coppel.com/l/sitemap/perfumes-cosmeticos.xml",
]
_PRODUCTS_PER_SHARD = 300

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


class CoppelMxSpider(scrapy.Spider):
    name = "coppel_mx"
    allowed_domains = ["coppel.com"]
    currency = "MXN"
    language = "es"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }
    IMPERSONATE_PROFILE = "chrome124"

    async def start(self):
        for shard_url in _SHARDS:
            yield scrapy.Request(
                shard_url,
                callback=self.parse_shard,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_shard(self, response):
        urls = _LOC_RE.findall(response.text)[:_PRODUCTS_PER_SHARD]
        logger.info("coppel_mx: %s -> %d product urls", response.url, len(urls))
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            return
        product = data.get("props", {}).get("pageProps", {}).get("product")
        if not isinstance(product, dict):
            return

        name = product.get("name")
        sku = product.get("sku")
        price = (product.get("price") or {}).get("discountedPrice") or (
            product.get("price") or {}
        ).get("salesPrice")
        if not name or not sku or price is None:
            return

        breadcrumb = product.get("breadcrumb") or []
        category = breadcrumb[-1]["label"] if breadcrumb else None

        yield {
            "product_id": str(sku),
            "product_name": str(name)[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Confirmed
    # live 2026-08-18 on 2 PDPs (curl_cffi chrome124 impersonation --
    # plain requests/curl are reset by this site's WAF, matching the live
    # spider's own IMPERSONATE_PROFILE): a server-rendered Product JSON-LD
    # block is present alongside the `__NEXT_DATA__` blob the live parse
    # reads, so the shared jsonld tier covers this spider on its own. Falls
    # back to `__NEXT_DATA__` (the live parse's own logic) for older/newer
    # snapshots that may lack the JSON-LD tag.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived Coppel PDP page."""
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

        m = _NEXT_DATA_RE.search(html_text)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            return
        product = data.get("props", {}).get("pageProps", {}).get("product")
        if not isinstance(product, dict):
            return
        name = product.get("name")
        sku = product.get("sku")
        price = (product.get("price") or {}).get("discountedPrice") or (
            product.get("price") or {}
        ).get("salesPrice")
        if not name or not sku or price is None:
            return
        breadcrumb = product.get("breadcrumb") or []
        category = breadcrumb[-1]["label"] if breadcrumb else None
        yield {
            "product_id": str(sku),
            "product_name": str(name)[:500],
            "category": category,
            "price": str(price),
            "currency": cls.currency,
            "available": True,
            "url": url,
            "language": cls.language,
        }
