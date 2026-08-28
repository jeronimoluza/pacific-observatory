"""
Spider for OLX Pakistan (www.olx.com.pk) -- consumer-goods classifieds.

Server-rendered listing cards (React-hydrated, but the initial HTML already
carries real listing data — no JS execution needed). Each card sits inside
an `<article>` and exposes stable `aria-label` markers regardless of the
site's obfuscated CSS-module class hashes:
  <article ...>
    <a href="/item/gaming-phone-xiaomi-mi-redmi-poco-cellarena-iid-1115377837"
       title="Gaming Phone XIAOMI Mi Redmi Poco - CELLARENA">...</a>
    <div aria-label="Price" ...><span ...>Rs 60,000</span></div>

Prices render either as plain "Rs 60,000" (comma-grouped) or, for
higher-value listings, "Rs 1.48 Lac" (lakh = 100,000) / "Rs 2.55 Crore"
(crore = 10,000,000) — both confirmed live on category pages.

Category pagination is `?page=N` (confirmed working through at least page 5
on electronics-home-appliances_c99). Scoped to consumer-goods top-level
categories only (electronics, appliances, computers, fashion, furniture,
etc.) — vehicles, real estate, jobs and services are excluded as out of
scope for a retail price basket (pakwheels.com covers used vehicles
separately).

Re-verified live 2026-08-17: GET https://www.olx.com.pk/ -> 200, 8.5MB SSR
HTML with real "Rs 60,000"-style PKR listing prices throughout (matches the
shard's probe). GET one category page -> 200, 33 distinct cards.
"""

import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.olx.com.pk"
_CATEGORIES = [
    "electronics-home-appliances_c99",
    "computers-accessories_c443",
    "tv-video-audio_c729",
    "cameras-accessories_c727",
    "fashion-beauty_c87",
    "footwear_c224",
    "clothes_c642",
    "furniture-home-decor_c628",
    "home-decoration_c575",
    "musical-instruments_c714",
    "books-magazines_c453",
    "kids-accessories_c235",
    "kids-furniture_c231",
    "sports-equipment_c100",
    "pet-food-accessories_c175",
    "health-beauty_c741",
    "gym-fitness_c771",
    "games-entertainment_c93",
]
# Bench 2026-08-17 (smoke, cap=8): 5 category page-1 fetches (2.8-3.1MB
# each) in 8.2s wall at CONCURRENT_REQUESTS_PER_DOMAIN=6 -- 8 pages/category
# was far under budget. Raised to 60; worst case (all 18 categories hit the
# cap) is 1,080 requests, ~6-10min at the observed per-request cost, well
# inside the 25min budget. Each category still self-limits via the
# `if n > 0` check below once its real page depth is exhausted.
MAX_PAGES = 60

_ARTICLE_START_RE = re.compile(r"<article ")
_ITEM_RE = re.compile(r'href="(/item/[^"]*-iid-(\d+))"[^>]*title="([^"]*)"')
_PRICE_RE = re.compile(r'aria-label="Price"[^>]*>\s*<span[^>]*>([^<]*)</span>')

_UNIT_MULTIPLIERS = {
    "lac": 100_000,
    "lacs": 100_000,
    "crore": 10_000_000,
    "cr": 10_000_000,
}


def _parse_price(raw: str):
    text = raw.replace("Rs", "").strip()
    parts = text.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].lower() in _UNIT_MULTIPLIERS:
        number, unit = parts
        try:
            return float(number.replace(",", "")) * _UNIT_MULTIPLIERS[unit.lower()]
        except ValueError:
            return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


class OlxPkSpider(scrapy.Spider):
    name = "olx_pk"
    allowed_domains = ["olx.com.pk"]
    currency = "PKR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 6,
        "DOWNLOAD_DELAY": 0.2,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                f"{_BASE}/{slug}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": 1},
            )

    def parse_listing(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        starts = [m.start() for m in _ARTICLE_START_RE.finditer(response.text)]
        starts.append(len(response.text))
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        seen_ids = set()
        for i in range(len(starts) - 1):
            block = response.text[starts[i] : starts[i + 1]]
            item_m = _ITEM_RE.search(block)
            price_m = _PRICE_RE.search(block)
            if not (item_m and price_m):
                continue
            item_id = item_m.group(2)
            if item_id in seen_ids:
                continue
            price = _parse_price(price_m.group(1))
            if price is None:
                continue
            seen_ids.add(item_id)
            n += 1
            yield {
                "product_id": item_id,
                "product_name": html.unescape(item_m.group(3)).strip()[:500],
                "category": slug.rsplit("_c", 1)[0],
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": urljoin(_BASE, item_m.group(1)),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: {slug} page={page} cards={n}")

        if n > 0 and page < MAX_PAGES:
            yield scrapy.Request(
                f"{_BASE}/{slug}?page={page + 1}",
                callback=self.parse_listing,
                meta={"slug": slug, "page": page + 1},
            )
