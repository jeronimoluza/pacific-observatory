"""bakuelectronics.az -- Azerbaijan electronics/appliances retailer, Next.js
pages router (COICOP: mixed, electronics/home dept-store-like).

Verified live 2026-08-17: plain curl_cffi impersonate=chrome124, zero auth,
zero session/cookies needed. The onboarding probe's negative verdict was
right that the homepage's __NEXT_DATA__ only carries homeTopSlider banners
(no per-product prices) -- but wrong to stop there. Individual product pages
(``/mehsul/<slug>-<numeric-id>``) ARE server-rendered with a full
``prodDetails`` object (id, title, price, brand_name, breadcrumb, status,
quantity) inside their own ``__NEXT_DATA__``.

Catalog enumeration is sitemap-driven, not category-pagination-driven: the
site's sitemap index (https://bakuelectronics.az/sitemap.xml) lists 7 shards
(sitemap-0.xml .. sitemap-6.xml), each ~5,000 URLs with ~4,600 ``/mehsul/``
product URLs verified live in shard 0 alone -- ~30k+ products across all
shards, satisfying the enumerability requirement without needing a walkable
listing page (there is none; the homepage carries no real catalog).

``breadcrumb`` on the product gives the category chain (second-to-last
entry; the last entry is the product's own title, no ``slug`` key).
``status`` (bool) is used for ``available``.

A handful of sitemap URLs are stale (one verified 404 in shard 0); the
spider simply drops those responses rather than failing the whole shard.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

_SITEMAP_INDEX = "https://bakuelectronics.az/sitemap.xml"


class BakuelectronicsAzSpider(scrapy.Spider):
    name = "bakuelectronics_az"
    allowed_domains = ["bakuelectronics.az"]
    currency = "AZN"
    language = "az"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_SITEMAP_INDEX, callback=self.parse_sitemap_index)

    def parse_sitemap_index(self, response):
        shard_urls = _LOC_RE.findall(response.text)
        logger.info(f"bakuelectronics_az: {len(shard_urls)} sitemap shards")
        for url in shard_urls:
            yield scrapy.Request(url, callback=self.parse_product_sitemap)

    def parse_product_sitemap(self, response):
        urls = [u for u in _LOC_RE.findall(response.text) if "/mehsul/" in u]
        logger.info(f"bakuelectronics_az: {response.url} -> {len(urls)} product URLs")
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_product)

    def parse_product(self, response):
        if response.status == 404:
            return

        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            return
        try:
            data = json.loads(m.group(1))
        except ValueError:
            logger.warning(
                f"bakuelectronics_az: unparseable __NEXT_DATA__ on {response.url}"
            )
            return

        pd = data.get("props", {}).get("pageProps", {}).get("prodDetails")
        if not isinstance(pd, dict):
            return

        name = pd.get("title")
        price = pd.get("price")
        product_id = pd.get("productCode") or pd.get("id")
        if not name or price is None or product_id is None:
            return

        breadcrumb = pd.get("breadcrumb") or []
        category = breadcrumb[-2]["name"] if len(breadcrumb) >= 2 else None

        yield {
            "product_id": str(product_id),
            "product_name": str(name)[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(pd.get("status", True)),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
