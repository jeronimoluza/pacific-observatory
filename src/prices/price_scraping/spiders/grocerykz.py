"""
Spider for GroceryKZ (Kazakhstan) — https://grocerykz.com/.

Bitrix-powered, server-rendered category pages under /catalog/<...>/. The
site's own nav exposes ~300 nested category URLs; the companion
`_grocerykz_categories.txt` (230 lines) keeps only leaf paths (no path that
is itself a prefix of a longer path), since a parent category's products
are already covered by its children. No pagination was observed: a small
category (7 products) and a larger one (24 products) both rendered their
full set in one response, and `?PAGEN_1=2` returned byte-different but
count-identical (same products) content rather than a next page — so each
leaf URL is fetched once.

Product cards render as `<div class="productTable">` blocks with a
`data-id` (numeric SKU), name, and `KZT`-suffixed price directly in the
listing HTML. Re-verified live 2026-08-06: /catalog/beverages/water/
still_water/ -> 200, 24 real products incl. 'Tassay still water, 5 l'
1 200 KZT.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://grocerykz.com"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_grocerykz_categories.txt"
_CARD_RE = re.compile(
    r'<div class="productTable">.*?'
    r'<a href="([^"]+)" class="picture">.*?data-id="(\d+)">Quick view.*?'
    r'class="name"><span class="middle">([^<]*)</span></a>\s*'
    r'<a class="price">\s*([\d\s]+?)\s*KZT',
    re.S,
)


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class GrocerykzSpider(scrapy.Spider):
    name = "grocerykz"
    allowed_domains = ["grocerykz.com"]
    currency = "KZT"
    language = "en"

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
        for path in _load_categories():
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_category,
                meta={"category_path": path},
            )

    def parse_category(self, response):
        category = response.meta["category_path"].strip("/")
        cards = _CARD_RE.findall(response.text)
        logger.info(f"grocerykz: {category} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, product_id, name, price in cards:
            yield {
                "product_id": product_id,
                "product_name": name.strip()[:500],
                "category": category.replace("/", " > "),
                "price": price.replace(" ", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
