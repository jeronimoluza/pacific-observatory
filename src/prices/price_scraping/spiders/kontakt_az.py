"""kontakt.az -- Azerbaijan electronics/appliances retailer, Magento 2
(Swissup Breeze theme) (COICOP: mixed, dept-store-like electronics/home).

Verified live 2026-08-17: curl_cffi impersonate=chrome124 clears cleanly
(bare curl gets cf-mitigated:challenge). /rest/V1/products 401s (no token)
and POSTs to /graphql are themselves Cloudflare-challenged even with a warm
cookie jar, so this spider does NOT use MagentoRestBaseSpider or
MagentoGraphQLBaseSpider -- it crawls the server-rendered Swissup Breeze
category listing HTML directly (a standalone spider, not the shared Magento
base, since neither of its two surfaces fit here).

Each category listing page embeds one clean per-tile GTM datalayer blob:
  <div class="prodItem product-item" id="67871" data-sku="TM-DG-SBP-1105-SM-2468"
       data-gtm='{"item_name":"iPhone 15 128 GB Blue","item_id":"...",
                  "item_brand":"Apple","price":1819.99,"item_category":"Smartfonlar",
                  "item_category2":"Telefoniya",...}'>
    ... <a href="https://kontakt.az/iphone-15-128-gb-blue" title="..."
           data-url-prolabels="..." class="prodItem__img ...">
-- id/sku/name/brand/price/category all come from that JSON, not from the
visible "1.999,99 ₼" / "1.819,99 ₼" markup (a naive regex on an
unrelated inline JSON field elsewhere on the page returned the wrong number
during the onboarding probe; the GTM blob is the reliable signal). The
product URL is recovered by a second regex over the same tile order (the
image-link anchor with data-url-prolabels immediately follows each tile in
document order) and zipped by index -- verified live to produce
identical-length, correctly-ordered id/url pairs.

Enumerability verified live: /telefoniya/smartfonlar (page 1, no ``p``
param) and .../telefoniya/smartfonlar?p=2 each returned 20 distinct tile
ids, ZERO overlap.

Category coverage is a fixed list of leaf paths recovered from live
homepage promo banners (no reachable full nav/sitemap category list found
in the time budget) -- thin but real; not an exhaustive crawl.
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_TILE_RE = re.compile(
    r'<div class="prodItem product-item" id="(\d+)" data-sku="([^"]*)" data-gtm=\'([^\']+)\''
)
_URL_RE = re.compile(
    r'<a href="(https://kontakt\.az/[^"]+)" title="[^"]*" data-url-prolabels'
)

_CATEGORIES = (
    "telefoniya/smartfonlar",
    "ev-ve-bag/hovuz-ve-avadanliqlar/hovuzlar",
    "geyim-ayaqqabi-ve-aksessuarlar/geyim-aksessuarlari",
    "saatlar-ve-qulaqliqlar/saatlar/smart-saatlar",
    "neqliyyat-vasiteleri/neqliyyat/velosipedler",
    "bag-aletleri",
)

MAX_PAGES = 20


class KontaktAzSpider(scrapy.Spider):
    name = "kontakt_az"
    allowed_domains = ["kontakt.az"]
    currency = "AZN"
    language = "az"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.5,
        "RETRY_TIMES": 5,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"https://kontakt.az/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        tiles = _TILE_RE.findall(response.text)
        urls = _URL_RE.findall(response.text)
        n = min(len(tiles), len(urls))
        logger.info(
            f"kontakt_az: {slug} page={page} tiles={len(tiles)} urls={len(urls)}"
        )

        scraped_at = datetime.now(timezone.utc).isoformat()
        for i in range(n):
            product_id, sku, gtm_raw = tiles[i]
            url = urls[i]
            item = self._parse_item(product_id, sku, gtm_raw, url, scraped_at)
            if item is not None:
                yield item

        if n > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"https://kontakt.az/{slug}?p={nxt}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": nxt},
            )

    def _parse_item(
        self, product_id: str, sku: str, gtm_raw: str, url: str, scraped_at: str
    ) -> dict | None:
        try:
            gtm = json.loads(html.unescape(gtm_raw))
        except ValueError:
            return None

        name = gtm.get("item_name")
        price = gtm.get("price")
        if not name or price is None:
            return None

        category = gtm.get("item_category2") or gtm.get("item_category") or None

        return {
            "product_id": product_id,
            "product_name": html.unescape(str(name)).strip()[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
