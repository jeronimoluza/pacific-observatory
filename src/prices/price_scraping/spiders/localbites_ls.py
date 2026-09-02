"""
Spider for LocalBites -- a multi-vendor food-delivery marketplace serving
Maseru, Lesotho (store.localbites.co.ls). Discovered via the workbook
candidate "LocalBites Lesotho"; at survey time groceries were flagged
"coming soon" -- re-verified live 2026-09-01 and there is still no
"Groceries" category (categories/groceries*, /categories/supermarket all
resolve 200 with "No Products found" -- the placeholder has not shipped).
The two live top-level categories are "Food" (fast-food/cafe delivery,
~389 products) and "Liquor" (~69 products).

The platform's own directory (api.localbites.co.ls/api/stores, a genuine
open JSON API, no auth) lists 14 named first-party merchants -- Barcelos,
BiteLiqour, Boba Heaven, Debonairs (Pioneer Mall), Foso Foods, Golden City
Palace, Highlands Bliss, Hungry Lion, KFC, Lecholi Family Restaurant,
Purple Coffee, Stadium Fast Foods Main North, Steers, Trout Fish Market.
All but BiteLiqour are restaurants/QSR chains or cafes selling PREPARED
MEALS, not grocery SKUs -- "Trout Fish Market" is a fish-and-chips eatery,
not a fresh-fish market, confirmed by its product list ("Trout wrap",
"Half Chicken With Chips"). None of these are supermarkets, so this whole
source is genuinely channel=marketplace, not a food-retail channel per the
project's channel taxonomy -- it does not count toward the food-source bar,
but it is a real, working, LSL-denominated price source (mostly COICOP 11
restaurant meals) and Lesotho had zero marketplace-of-restaurants coverage
before this.

BiteLiqour is DELIBERATELY EXCLUDED from this walk -- it is onboarded
separately as bite_liqour_ls (channel=specialty-food, the single-merchant-
on-an-aggregator pattern) so its rows are not double-collected under two
source keys.

Two-step crawl: (1) GET api.localbites.co.ls/api/stores -> JSON directory
of all stores + slugs (Tier 1B). (2) For each non-BiteLiqour store slug,
GET store.localbites.co.ls/stores/<slug> and parse the embedded
__NEXT_DATA__ JSON blob's pageProps.initialProducts.data.data[] (same
Next.js SSR shape as bite_liqour_ls).

KNOWN LIMITATION (same as _wolt_base and bite_liqour_ls): each store page's
SSR payload is capped at page 1 of that store's own listing; ?page=N is
accepted but silently re-served as page 1. Larger stores (KFC: 62 products,
Stadium Fast Foods: 53, Steers: 49, Lecholi: 50) are therefore undercounted
at ~24 rows each. This is a whole-catalog-of-what's-reachable walk, not a
targeted extractor.
"""

import json
import logging
import re

from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_STORES_API = "https://api.localbites.co.ls/api/stores"
_STORE_URL_TMPL = "https://store.localbites.co.ls/stores/{slug}"
_EXCLUDE_SLUGS = {"biteliqour"}  # onboarded separately as bite_liqour_ls
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


class LocalbitesLsSpider(scrapy.Spider):
    name = "localbites_ls"
    allowed_domains = ["api.localbites.co.ls", "store.localbites.co.ls"]
    currency = "LSL"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            _STORES_API, callback=self.parse_stores, errback=self.errback
        )

    def parse_stores(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(f"{self.name}: /api/stores did not parse as JSON")
            return
        stores = payload.get("data", {}).get("data", [])
        logger.info(f"{self.name}: {len(stores)} stores in directory")
        for store in stores:
            slug = store.get("slug")
            if not slug or slug in _EXCLUDE_SLUGS:
                continue
            url = _STORE_URL_TMPL.format(slug=slug)
            yield scrapy.Request(
                url,
                callback=self.parse_store,
                errback=self.errback,
                cb_kwargs={"store_name": store.get("name")},
            )

    def parse_store(self, response, store_name=None):
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning(f"{self.name}: no __NEXT_DATA__ blob at {response.url}")
            return
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.warning(
                f"{self.name}: __NEXT_DATA__ did not parse at {response.url}"
            )
            return
        products = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialProducts", {})
            .get("data", {})
            .get("data", [])
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for p in products:
            title = p.get("title")
            slug = p.get("slug")
            price = p.get("special_price") or p.get("price")
            if not title or price in (None, 0) or not slug:
                continue
            n += 1
            yield {
                "product_id": str(p.get("id")),
                "product_name": str(title).strip()[:500],
                "category": p.get("category_name"),
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("availability", True)),
                "url": f"https://store.localbites.co.ls/products/{slug}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(
            f"{self.name}: {n} items from store '{store_name}' ({response.url})"
        )

    def errback(self, failure):
        logger.error(
            f"{self.name}: request failed {failure.request.url} — {failure.value!r}"
        )
