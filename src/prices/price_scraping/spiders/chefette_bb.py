"""
Chefette Restaurants Ltd (Barbados) — https://chefette.com/.

Bajan fast-food chain (Chefette fried chicken/pizza/rotis + its BBQ Barn
steakhouse brand), HQ'd in Barbados with a +1-246 (Barbados) phone prefix
and no country selector on the site — single-country chain, unlike the
multi-Caribbean Automotive Art franchise found in the same search pass.

The rendered menu page (`/menu/<brand>`) is a Vue SPA shell with no prices
in raw HTML, but its own network trace (Playwright, 2026-09-01) shows it
calls a plain JSON API with no auth and no cookies:

    GET https://chefette.com/api/v2/food/chefette   (137 items, 13 categories)
    GET https://chefette.com/api/v2/food/barn        (64 items, 7 categories)

Both confirmed replayable cold with curl_cffi impersonate=chrome124, zero
headers beyond the default UA. `/api/v2/cart` by contrast 403s
("Unauthenticated Cart API requests are not allowed!") — the menu-read API
and the order-write API have different auth gates; only the former is
scraped here.

Item shape: {"name","microsNo","description","image","badges","price":"$X.XX",
"isBarn","isAppExclusive"}. `microsNo` is the POS item code — stable id.
Prices arrive as a "$"-prefixed string; strip the symbol. No per-item URL
exists (SPA is a single page per brand) — item URL is synthesised as
`<category url>#<microsNo>` per the DuplicationPipeline url-dedup rule
(plain category URL would collide across every item in that category).

Analytical note: this is `channel: other` (dining/restaurant), matching the
GLOSSARY.md precedent for hotpepper_jp — it does NOT count as a food
channel for the programme's supermarket/hypermarket/etc. count, only toward
the source total.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://chefette.com"
BRANDS = {
    "chefette": "Chefette",
    "barn": "BBQ Barn",
}


class ChefetteBbSpider(scrapy.Spider):
    name = "chefette_bb"
    allowed_domains = ["chefette.com"]
    currency = "BBD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for brand_slug in BRANDS:
            yield scrapy.Request(
                f"{BASE_URL}/api/v2/food/{brand_slug}",
                callback=self.parse_menu,
                errback=self.errback,
                meta={"brand_slug": brand_slug},
            )

    def parse_menu(self, response):
        brand_slug = response.meta["brand_slug"]
        brand_name = BRANDS[brand_slug]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"{self.name}: non-JSON from {response.url}")
            return

        categories = (data.get("data") or {}).get("categories") or []
        seen_ids: set[str] = set()
        count = 0
        for cat in categories:
            cat_name = cat.get("name") or ""
            cat_url = cat.get("url") or f"{BASE_URL}/menu/{brand_slug}"
            for item in cat.get("items") or []:
                name = (item.get("name") or "").strip()
                pid = item.get("microsNo")
                price_raw = (
                    (item.get("price") or "").replace("$", "").replace(",", "").strip()
                )
                if not name or not pid or not price_raw:
                    continue
                try:
                    float(price_raw)
                except ValueError:
                    continue
                # The same microsNo is cross-listed in several menu categories
                # (e.g. a combo shown under both its home category and
                # "Specials") -- same product, same price, not a distinct
                # SKU. Keep only the first (home-category) occurrence so the
                # row count reflects real menu items, not category placements.
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                yield {
                    "product_id": f"{brand_slug}_{pid}",
                    "product_name": f"{brand_name} {name}"[:500],
                    "category": cat_name,
                    "price": price_raw,
                    "currency": self.currency,
                    "available": True,
                    "url": f"{cat_url}#{pid}",
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }
                count += 1

        logger.info(f"{self.name}: brand={brand_slug} items={count}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
