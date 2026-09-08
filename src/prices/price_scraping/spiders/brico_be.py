"""
Spider for Brico Belgium -- https://www.brico.be/.

DIY / home-improvement retailer. Homepage and category-hub pages
(`/fr/<...>/wc1/`) are fully client-rendered -- no product links or price
text anywhere in the server HTML, only "conseils bricolage" content links.
No API discovered for category enumeration.

`/sitemap.xml` -> `/fr/bricoproductpagessitemapindex{1..8}.xml` (+ `/nl/`
duplicates) lists ~50k direct PDP urls per shard. Each PDP carries a
`schema.org/Product` JSON-LD block with a real EUR price. Verified live
2026-09-06: PDP `.../peinture-murale-perfection-mur-plafond-blanc-mat-10l/
5299353` has `"price":59.99`. Spider walks the `/fr/` PDP sitemap shards
only (stride-sampled) to avoid double-counting the `/nl/` duplicates.
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP_INDEX = "https://www.brico.be/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_LD_JSON_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_PDP_STRIDE = 40  # sample every Nth PDP across ~400k fr PDPs (8 x 50k)


class BricoBeSpider(scrapy.Spider):
    name = "brico_be"
    allowed_domains = ["brico.be"]
    currency = "EUR"
    language = "fr"

    IMPERSONATE_PROFILE = "chrome124"

    custom_settings = {
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_impersonate.middleware.RandomBrowserMiddleware": None,
            "price_scraping.middlewares.CustomUserAgentMiddleware": None,
        },
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP_INDEX,
            callback=self.parse_sitemap_index,
            meta={"impersonate": self.IMPERSONATE_PROFILE},
        )

    def parse_sitemap_index(self, response):
        shards = [
            loc if loc.startswith("http") else response.urljoin(loc)
            for loc in _LOC_RE.findall(response.text)
        ]
        product_shards = [s for s in shards if "bricoproductpagessitemapindex" in s and "/fr/" in s]
        logger.info("brico_be: %d fr product-sitemap shards", len(product_shards))
        for shard in product_shards:
            yield scrapy.Request(
                shard,
                callback=self.parse_sitemap_shard,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_sitemap_shard(self, response):
        product_urls = _LOC_RE.findall(response.text)
        sampled = product_urls[::_PDP_STRIDE]
        logger.info(
            "brico_be: sampled %d/%d PDP urls from %s",
            len(sampled), len(product_urls), response.url,
        )
        for url in sampled:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": self.IMPERSONATE_PROFILE},
            )

    def parse_product(self, response):
        product = None
        for block in _LD_JSON_RE.findall(response.text):
            try:
                data = json.loads(block)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data.get("@type") == "Product":
                product = data
                break

        if not product:
            return

        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = offers.get("price")
        name = product.get("name")
        if not name or price in (None, "", 0):
            return

        yield {
            "product_id": product.get("sku") or product.get("mpn") or response.url,
            "product_name": str(name).strip()[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": "InStock" in str(offers.get("availability") or ""),
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
