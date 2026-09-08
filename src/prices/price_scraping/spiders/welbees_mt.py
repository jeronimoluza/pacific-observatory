"""
Welbee's (Malta) — https://welbees.mt/.

Shard AI_NOTES/host were both wrong: `welbees.com.mt` does not resolve
(DNS NXDOMAIN across all five curl_cffi impersonation profiles) and the
site is not WooCommerce. The live domain is `welbees.mt` (no `.com`), a
bespoke Tailwind-styled storefront that renders products server-side —
plain `curl_cffi` (no Playwright) returns the full product grid.

Category pages: /shop/category/<D-code>/<slug>?page=N. Each product card is
a `div.product-main-holder[data-product-code]`; price sits in the first
`.text-tertiary` node inside the card (may carry a "/kg" unit suffix),
name+URL in the `a[href^="/item/"]` anchor. Verified real pagination:
page=1 vs page=2 on the Butcher Counter category returned 72 vs 72 fully
disjoint product codes; page links go up to page=3 for that category.

The homepage nav's `/cdn-cgi/challenge-platform/...` beacon suggested
Cloudflare, but it does not block plain HTTP — the front page and every
category page above returned HTTP 200 with full content under chrome124.

Currency EUR (Malta). Prices are plain decimal strings with a euro sign
and sometimes a per-kg suffix — parsed to a bare decimal here.

16 top-level categories enumerated from the homepage nav (2026-09-06).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://welbees.mt"

CATEGORIES = [
    ("D-5430", "baby"),
    ("D-5431", "bakery"),
    ("D-5432", "butcher-counter"),
    ("D-5433", "chilled-food"),
    ("D-5434", "delicatessen"),
    ("D-5435", "drinks"),
    ("D-5436", "food-cupboard"),
    ("D-5438", "frozen-food"),
    ("D-5439", "fruit-and-veg-counter"),
    ("D-5441", "health-and-beauty"),
    ("D-5442", "healthy-section"),
    ("D-5443", "home-and-entertainment"),
    ("D-5444", "household"),
    ("D-5445", "pets"),
    ("D-5446", "tobacco"),
    ("D-5447", "clothes-and-accessories"),
]

MAX_PAGES = 40  # safety cap per category
_PRICE_RE = re.compile(r"€\s?([\d,]+\.\d{2})")


class WelbeesMtSpider(scrapy.Spider):
    name = "welbees_mt"
    allowed_domains = ["welbees.mt"]
    currency = "EUR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for code, slug in CATEGORIES:
            yield scrapy.Request(
                f"{BASE}/shop/category/{code}/{slug}?page=1",
                callback=self.parse_category,
                errback=self.errback,
                meta={"code": code, "slug": slug, "page": 1},
            )

    def parse_category(self, response):
        code = response.meta["code"]
        slug = response.meta["slug"]
        page = response.meta["page"]
        soup = BeautifulSoup(response.text, "html.parser")
        holders = soup.select("div.product-main-holder[data-product-code]")
        found = 0
        for holder in holders:
            item = self._parse_card(holder, slug)
            if item:
                found += 1
                yield item
        logger.info(f"{self.name}: {slug} page={page} cards={len(holders)} yielded={found}")
        if holders and page < MAX_PAGES:
            yield scrapy.Request(
                f"{BASE}/shop/category/{code}/{slug}?page={page + 1}",
                callback=self.parse_category,
                errback=self.errback,
                meta={"code": code, "slug": slug, "page": page + 1},
            )

    def _parse_card(self, holder, category_slug):
        pid = holder.get("data-product-code")
        link = holder.select_one("a[href^='/item/']")
        if not link or not pid:
            return None
        name = link.get_text(strip=True)
        if not name:
            return None
        price_el = holder.select_one(".text-tertiary")
        if not price_el:
            return None
        match = _PRICE_RE.search(price_el.get_text(" ", strip=True))
        if not match:
            return None
        price = match.group(1).replace(",", "")
        try:
            if float(price) == 0:
                return None
        except ValueError:
            return None
        href = link.get("href")
        return {
            "product_id": pid,
            "product_name": name[:500],
            "category": category_slug,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": f"{BASE}{href}" if href.startswith("/") else href,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
