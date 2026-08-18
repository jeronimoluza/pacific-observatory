"""hepsiburada.com -- Turkey's largest general marketplace (COICOP: mixed, marketplace).

Verified live 2026-08-17: curl_cffi impersonate=chrome124/chrome120/safari17_0
all clear cleanly (bare curl hit Akamai's HBBlockandCaptcha.html) -- this
spider relies on the project-wide default chrome120 TLS impersonation
(RandomBrowserMiddleware + CompositeDownloadHandler in settings.py already
impersonate every request; no per-spider override needed).

The earlier probe only saw homepage carousels (curated, unpaginated). The
real catalog is reachable via the site's own category sitemap
(https://www.hepsiburada.com/sitemaps/category/sitemap.xml ->
sitemap_1.xml), which lists ~6,000 real leaf category URLs of the form
https://www.hepsiburada.com/<slug>-c-<id>. Each category page embeds a clean
JSON-LD ItemList (<script type="application/ld+json"> with @type ItemList)
of up to 36 Product entries -- sku, name, url, offers.price/priceCurrency --
no HTML tile parsing needed.

Enumerability verified live: /dus-setleri-c-18021971 (page 1) and
/dus-setleri-c-18021971?sayfa=2 returned 36 distinct SKUs each, ZERO overlap.

Pagination is the query param ``sayfa`` (Turkish "page"), 1-indexed; a page
whose ItemList comes back empty ends that category's walk.

Hepsiburada mixes first-party and third-party marketplace listings with no
reliable per-row seller signal in the JSON-LD -- manifest ships as
channel: marketplace, coicop_codes unset.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_ITEMLIST_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL
)

_SITEMAP_INDEX = "https://www.hepsiburada.com/sitemaps/category/sitemap.xml"
MAX_CATEGORIES = 200
MAX_PAGES = 20


class HepsiburadaTrSpider(scrapy.Spider):
    name = "hepsiburada_tr"
    allowed_domains = ["hepsiburada.com"]
    currency = "TRY"
    language = "tr"

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
        for url in shard_urls:
            yield scrapy.Request(url, callback=self.parse_category_sitemap)

    def parse_category_sitemap(self, response):
        urls = _LOC_RE.findall(response.text)[:MAX_CATEGORIES]
        logger.info(f"hepsiburada_tr: {len(urls)} category URLs to walk")
        for url in urls:
            yield scrapy.Request(
                url, callback=self.parse_listing, meta={"category_url": url, "page": 1}
            )

    def parse_listing(self, response):
        category_url = response.meta["category_url"]
        page = response.meta["page"]

        items = self._extract_items(response.text)
        logger.info(f"hepsiburada_tr: {category_url} page={page} items={len(items)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for entry in items:
            item = self._parse_item(entry, scraped_at)
            if item is not None:
                yield item

        if items and page < MAX_PAGES:
            nxt = page + 1
            sep = "&" if "?" in category_url else "?"
            yield scrapy.Request(
                f"{category_url}{sep}sayfa={nxt}",
                callback=self.parse_listing,
                meta={"category_url": category_url, "page": nxt},
            )

    def _extract_items(self, body: str) -> list:
        for block in _ITEMLIST_RE.findall(body):
            try:
                data = json.loads(block)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                return data.get("itemListElement", [])
        return []

    def _parse_item(self, entry: dict, scraped_at: str) -> dict | None:
        product = entry.get("item") or {}
        name = product.get("name")
        url = product.get("url")
        sku = product.get("sku")
        offers = product.get("offers") or {}
        price = offers.get("price")
        if not name or not url or not sku or price is None:
            return None

        return {
            "product_id": str(sku),
            "product_name": str(name)[:500],
            "category": None,
            "price": str(price),
            "currency": offers.get("priceCurrency") or self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
