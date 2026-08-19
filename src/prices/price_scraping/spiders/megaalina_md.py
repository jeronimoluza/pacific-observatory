"""
Spider for Mega Alina (Moldova) — https://www.megaalina.md/.

Custom PHP storefront. Category pages are server-rendered: e.g.
/ro/catalog/lapte -> 200, 508KB, real product cards with MDL prices
('16.15 MDL', '20.99 MDL', ...), re-verified live 2026-08-06. Pagination is
`?page=N`, stop when a page returns zero product cards.

Category discovery: the homepage nav exposes 344 `/ro/catalog/<slug>` links
spanning food, household, and general merchandise -- walked in full per the
whole-catalog-not-a-food-subset rule; see `_megaalina_md_categories.txt`.

Product cards: `<div class="goods-item">...<a href="URL"><img ... alt="NAME">
...<span class="price-current">PRICE MDL</span>`.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.megaalina.md"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_megaalina_md_categories.txt"
_CARD_RE = re.compile(
    r'class="goods-item">.*?href="([^"]+)">\s*<img[^>]*alt="([^"]*)".*?'
    r'class="price-current">([0-9.]+)\s*MDL',
    re.S,
)
MAX_PAGES = 50  # safety cap


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class MegaalinaMdSpider(scrapy.Spider):
    name = "megaalina_md"
    allowed_domains = ["megaalina.md"]
    currency = "MDL"
    language = "ro"

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
        for slug in _load_categories():
            yield scrapy.Request(
                f"{_BASE}/ro/catalog/{slug}",
                callback=self.parse_category,
                meta={"category": slug, "page": 1},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"megaalina_md: {category} page={page} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            yield {
                "product_id": url_path.rstrip("/").rsplit("/", 1)[-1],
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url_path
                if url_path.startswith("http")
                else f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if cards and page < MAX_PAGES:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}/ro/catalog/{category}?page={next_page}",
                callback=self.parse_category,
                meta={"category": category, "page": next_page},
            )
