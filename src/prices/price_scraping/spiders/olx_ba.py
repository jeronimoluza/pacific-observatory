"""
Spider for olx.ba (rebranded on-site as "PIK.ba") — Bosnia and Herzegovina
general classifieds marketplace.

Verified live 2026-09-06: the site is a Nuxt SPA whose homepage ships empty
state; the real catalog lives behind a separate open JSON API at
https://api.olx.ba. `/search?page=N` (no auth, no cookies, plain curl_cffi
chrome124) returns 20 hits/page across ALL categories (vehicles, real
estate, electronics, home goods, services, jobs) with `meta.total` = 6.8M
listings nationwide (`last_page` ~340,897 at time of writing). Each hit
carries a numeric `price` field already in BAM (site displays "KM"), so no
string-parsing of a "1.350 KM"-style display string is needed — `price`
(int) is used directly, `display_price` is discarded.

`show_price` is False and/or `price` is 0/null for "Po dogovoru"
(negotiable) and boosted/promotional listings — dropped rather than
emitted as a fake price.

Confirmed page 2 returns a distinct set of listing ids from page 1 (real
pagination, not a cached/fixed page).

Pagination capped at MAX_PAGES, matching the tayara_tn precedent for
general classifieds sites where the full catalog would badly exceed the
run budget.

coicop_classification left as classifier — general classifieds mixing
vehicles/real-estate/electronics/services, no single COICOP prefix
applies. channel: marketplace (seller-authored listing titles).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://api.olx.ba/search"
MAX_PAGES = 150


class OlxBaSpider(scrapy.Spider):
    name = "olx_ba"
    allowed_domains = ["olx.ba", "api.olx.ba"]
    currency = "BAM"
    language = "bs"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Accept-Language": "bs-BA,bs;q=0.9,en;q=0.8",
            "Referer": "https://olx.ba/",
        },
    }

    async def start(self):
        for page in range(1, MAX_PAGES + 1):
            yield scrapy.Request(
                f"{_BASE}?page={page}",
                callback=self.parse_page,
                meta={"page": page},
            )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning("olx_ba: non-JSON response on page=%s", page)
            return
        hits = data.get("data") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for hit in hits:
            title = hit.get("title")
            price = hit.get("price")
            hit_id = hit.get("id")
            slug = hit.get("slug") or ""
            if not title or not hit.get("show_price", True):
                continue
            try:
                price_val = float(price)
            except (TypeError, ValueError):
                continue
            if price_val <= 0:
                continue
            n += 1
            yield {
                "product_id": str(hit_id),
                "product_name": str(title).strip()[:500],
                "category": hit.get("category_id"),
                "price": str(price_val),
                "currency": self.currency,
                "available": True,
                "url": f"https://olx.ba/artikal/{slug}-{hit_id}"
                if slug
                else f"https://olx.ba/artikal/{hit_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: page={page} hits={n}")
