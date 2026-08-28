"""
Spider for Denner (Switzerland) — https://www.denner.ch/de/weinshop.

Denner's main grocery assortment is physical-store-only (no online
groceries); the "Weinshop" (wine shop) section is the one part of the
site that actually sells online, and it is server-rendered (Nuxt SSR, not
a client-only shell): each result is a plain
`<div class="product-item stretch-link ...">` card carrying the title
(`product-item__title`), price (`price-tag__final-price`, format `51.–`
for whole francs or `47.70` otherwise) and permalink
(`href="/de/weinshop/<slug>~p<id>"`) directly in the raw HTML.

Re-verified live 2026-08-06: GET /de/weinshop/wein-sortiment -> 200,
1.13MB, 24 real products incl. 'Porta Leone Extra Dry Prosecco Superiore
Valdobbiadene DOCG' CHF 51.00 (id 1027181), 'Céline Rosé Côtes de Provence
AOC' CHF 47.70. Pagination via `?page=N` (page count seen up to 24 in the
listing's own links).

Narrow source: wine only (COICOP 02.1.1), not a full grocery catalog.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.denner.ch"
_START_PATHS = ["/de/weinshop/wein-sortiment", "/de/weinshop/wein-aktionen"]
_CARD_SPLIT_RE = re.compile(r'class="product-item stretch-link')
_TITLE_RE = re.compile(r"product-item__title[^>]*>([^<]+)<")
_PRICE_RE = re.compile(r'price-tag__final-price"[^>]*>([0-9.,]+)(?:.–|<)')
_HREF_RE = re.compile(r'href="(/de/weinshop/[^"]+~p(\d+))"')
MAX_PAGES = 30  # safety cap


class DennerChSpider(scrapy.Spider):
    name = "denner_ch"
    allowed_domains = ["denner.ch"]
    currency = "CHF"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        for path in _START_PATHS:
            yield scrapy.Request(
                f"{_BASE}{path}?page=1",
                callback=self.parse_page,
                meta={"path": path, "page": 1},
            )

    def parse_page(self, response):
        path = response.meta["path"]
        page = response.meta["page"]
        text = response.text
        starts = [m.start() for m in _CARD_SPLIT_RE.finditer(text)]
        if not starts:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for i, s in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(text)
            chunk = text[s:end]
            title_m = _TITLE_RE.search(chunk)
            price_m = _PRICE_RE.search(chunk)
            href_m = _HREF_RE.search(chunk)
            if not (title_m and price_m and href_m):
                continue
            price_raw = price_m.group(1).replace(",", ".")
            price = price_raw if "." in price_raw else f"{price_raw}.00"
            count += 1
            yield {
                "product_id": href_m.group(2),
                "product_name": title_m.group(1).strip()[:500],
                "category": "wine",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{href_m.group(1)}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"denner_ch: {path} page={page} items={count}")
        if count >= 20 and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}{path}?page={next_page}",
                callback=self.parse_page,
                meta={"path": path, "page": next_page},
            )
