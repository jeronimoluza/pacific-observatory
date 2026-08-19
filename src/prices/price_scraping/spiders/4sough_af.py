"""
Spider for 4sough.com (چهارسوق) — Afghanistan.

Next.js app-router SSR marketplace. No product API found (api.4sough.com
only serves image storage, /api/v1/products 404s), but the site publishes a
sitemap at https://4sough.com/sitemap_index/fa-sitemap/product.xml listing
12,422 product PDP URLs. Each PDP embeds a schema.org Product JSON-LD block
server-side with a real AggregateOffer (lowPrice/highPrice/priceCurrency),
confirmed live 2026-08-17: 'مت ورزشی یوگا' -> AFN 600, InStock. A sibling
BreadcrumbList JSON-LD gives the category path; the second-to-last entry is
the leaf category (last entry is the product name itself). No numeric SKU is
exposed anywhere on the page, so product_id is the URL slug (stable, unique
per the sitemap).

Re-verified live 2026-08-17: GET /sitemap_index/fa-sitemap/product.xml ->
200, 12,422 <loc> entries. GET one PDP -> 200, gzip 1MB / decoded 5.7MB
(recommendation rail bloats the page; gzip keeps the wire transfer small).
Mixed general-merchandise catalog (electronics, groceries, clothing,
home goods) per breadcrumb sampling.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterator
from urllib.parse import unquote

import scrapy

from ..archived import rows_from_jsonld

logger = logging.getLogger(__name__)

_PRODUCT_SITEMAP = "https://4sough.com/sitemap_index/fa-sitemap/product.xml"
# Each PDP renders a large recommendation rail (~5.7MB decoded, ~1MB gzip
# on the wire) that makes the full 12,422-URL sitemap take 2+ hours even at
# CONCURRENT_REQUESTS_PER_DOMAIN=24 (bench: 96.6 items/min). Capped to keep
# one collect run inside the ~25-minute budget; raise if that budget grows.
_MAX_PRODUCTS = 2200
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LDJSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>\s*(.*?)\s*</script>',
    re.DOTALL,
)


class FSoughAfSpider(scrapy.Spider):
    name = "4sough_af"
    allowed_domains = ["4sough.com"]
    currency = "AFN"
    language = "fa"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 24,
        "DOWNLOAD_DELAY": 0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_PRODUCT_SITEMAP, callback=self.parse_sitemap)

    def parse_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)[:_MAX_PRODUCTS]
        logger.info("4sough_af: %d product URLs in sitemap (capped)", len(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        product = None
        breadcrumb = None
        for block in _LDJSON_RE.findall(response.text):
            data = self._loads(block)
            if not isinstance(data, dict):
                continue
            if data.get("@type") == "Product":
                product = data
            elif data.get("@type") == "BreadcrumbList":
                breadcrumb = data

        if not product:
            return

        offers = product.get("offers") or {}
        price = offers.get("lowPrice") or offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0, "0"):
            return

        category = None
        if breadcrumb:
            items = breadcrumb.get("itemListElement") or []
            if len(items) >= 2:
                leaf = items[-2].get("item") or {}
                category = leaf.get("name")

        yield {
            "product_id": unquote(response.url.rsplit("/", 1)[-1]),
            "product_name": str(name).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": offers.get("availability", "").endswith("InStock"),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _loads(block):
        try:
            return json.loads(block)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). Confirmed
    # live 2026-08-18: the Product JSON-LD block on these PDPs uses an
    # AggregateOffer with lowPrice/highPrice directly, no nested `offers`
    # list -- `rows_from_jsonld`'s price extraction was widened to fall
    # back to `lowPrice` for exactly this shape (see archived.py). The
    # shared OpenGraph meta tier is deliberately NOT used as a fallback
    # here: this site's `og:title` is the SEO page title ("Buy X in
    # Afghanistan - 4sough"), not the clean product name -- confirmed on
    # 2 live pages -- so falling back to it would write polluted names.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived 4sough.com PDP page."""
        for row in rows_from_jsonld(html_text, url):
            row.setdefault("currency", cls.currency)
            row.setdefault("language", cls.language)
            yield row
