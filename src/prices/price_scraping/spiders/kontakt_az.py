"""kontakt.az -- Azerbaijan electronics/appliances retailer, Magento 2
(Swissup Breeze theme) (COICOP: mixed, dept-store-like electronics/home).

Verified live 2026-08-17: curl_cffi impersonate=chrome124 clears cleanly
(bare curl gets cf-mitigated:challenge). /rest/V1/products 401s (no token)
and POSTs to /graphql are themselves Cloudflare-challenged even with a warm
cookie jar, so this spider does NOT use MagentoRestBaseSpider or
MagentoGraphQLBaseSpider -- it crawls the server-rendered Swissup Breeze
category listing HTML directly (a standalone spider, not the shared Magento
base, since neither of its two surfaces fit here).

Re-platformed ~2026-10-07 to a headless front end (Magento now behind
api.kontakt.az): the GTM tiles below are gone, so name/price/URL come from
the server-rendered `product-card` markup, out-of-stock cards (no price)
are skipped, and product_id is the URL slug (no numeric id in the HTML).

Old (pre-2026-10) markup -- each category listing page embedded one clean
per-tile GTM datalayer blob:
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
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CARD_SPLIT_RE = re.compile(r'(?=<div class="product-card[ "])')
_HREF_RE = re.compile(r'class="product-card__name-row" href="(/[^"?]+)"')
_TITLE_RE = re.compile(r'class="product-card__title">([^<]+)<')
_PRICE_RE = re.compile(r'<span class="product-card__price">([\d.,]+) ₼<')
_CATEGORY_RE = re.compile(r'<h1 class="category-page__title">([^<]+)<')

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

        cards = _CARD_SPLIT_RE.split(response.text)[1:]
        cat_m = _CATEGORY_RE.search(response.text)
        category = html.unescape(cat_m.group(1)).strip() if cat_m else None
        logger.info(f"kontakt_az: {slug} page={page} cards={len(cards)}")

        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            item = self._parse_item(card, category, scraped_at)
            if item is not None:
                yield item

        if cards and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"https://kontakt.az/{slug}?p={nxt}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": nxt},
            )

    def _parse_item(
        self, card: str, category: str | None, scraped_at: str
    ) -> dict | None:
        href_m = _HREF_RE.search(card)
        title_m = _TITLE_RE.search(card)
        price_m = _PRICE_RE.search(card)
        if not (href_m and title_m and price_m):
            return None

        return {
            "product_id": href_m.group(1).strip("/"),
            "product_name": html.unescape(title_m.group(1)).strip()[:500],
            "category": category,
            "price": price_m.group(1).replace(",", ""),
            "currency": self.currency,
            "available": True,
            "url": f"https://kontakt.az{href_m.group(1)}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
