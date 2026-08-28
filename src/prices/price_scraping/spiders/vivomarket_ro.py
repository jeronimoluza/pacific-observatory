"""
Spider for VivoMarket (Romania) — https://www.vivomarket.ro/.

Gomag-platform storefront (Romanian e-commerce SaaS, gomagcdn.ro assets).
Category pages are server-rendered: e.g. /bacanie -> 200, 1.4MB, real product
cards with Lei prices ('44,40 Lei', '41,38 Lei', ...), re-verified live
2026-08-06. Pagination is `?p=N` (0-indexed: page 2 is `?p=1`), observed up
to 77 pages on the largest category. We stop a category when a page returns
zero product cards.

Category discovery: the homepage's rendered nav (`index.php?nc=tabs`, which
itself 404s but still returns the full site chrome) lists 208 top-level/
department slugs; 191 remain after dropping account/legal/utility pages
(blog, contact, wishlist, ...). See `_vivomarket_ro_categories.txt`. Carries
both retail and HoReCa (food-service bulk) lines per the source shard --
channel tagged supermarket since retail dominates.

Product cards: `<a href="URL" class="title _productUrl_<id> ..."
data-block="ListingName">NAME</a>` followed by
`<span class="text-main -g-product-box-final-price-<id>">PRICE Lei</span>`.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.vivomarket.ro"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_vivomarket_ro_categories.txt"
_CARD_RE = re.compile(
    r'<a href="([^"]+)"[^>]*class="title _productUrl_\d+[^"]*"[^>]*'
    r'data-block="ListingName">([^<]+)</a>.*?'
    r'class="text-main -g-product-box-final-price-\d+">\s*([0-9.,]+)\s*Lei',
    re.S,
)
MAX_PAGES = 100  # safety cap; largest observed category had 77 pages


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class VivomarketRoSpider(scrapy.Spider):
    name = "vivomarket_ro"
    allowed_domains = ["vivomarket.ro"]
    currency = "RON"
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
                f"{_BASE}/{slug}",
                callback=self.parse_category,
                meta={"category": slug, "page": 1},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"vivomarket_ro: {category} page={page} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            yield {
                "product_id": url_path.rstrip("/").rsplit("/", 1)[-1].split("?")[0],
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price.replace(".", "").replace(",", "."),
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
                f"{_BASE}/{category}?p={page}",
                callback=self.parse_category,
                meta={"category": category, "page": next_page},
            )
