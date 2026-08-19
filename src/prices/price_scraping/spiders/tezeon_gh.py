"""
Spider for Tezeon (Ghana) — https://tezeon.com/grocery.

A Playwright network trace on a category page surfaced a fully open
Django-REST-style JSON API at api.tezeon.com (reproduced standalone with
plain curl, no auth): GET /api/products/?page_size=100 -> 200, cursor
pagination via a `next` field that is already a complete follow-able URL.

General marketplace (electronics/fashion/home dominate the 295-category
tree) with a real "Groceries & Food" slice. Attempts to filter the products
endpoint to that one category (category=, category=groceries-food) 400'd
in the prior probe; category_slug=groceries-food does work, but per the
whole-catalog-walk convention we do not filter here — we walk every
product and let the downstream classifier route each item to its COICOP
leaf.
"""

import html
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_START_URL = "https://api.tezeon.com/api/products/?page_size=100"
MAX_PAGES = 300


class TezeonGhSpider(scrapy.Spider):
    name = "tezeon_gh"
    allowed_domains = ["tezeon.com"]
    currency = "GHS"
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
        yield scrapy.Request(
            _START_URL,
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"tezeon_gh: non-JSON response at page={page}")
            return
        data = payload.get("data") or {}
        products = data.get("results") or []
        logger.info(f"tezeon_gh page={page} count={len(products)}")
        if not products:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("final_price")
            if price is None:
                price = p.get("base_price")
            slug = p.get("slug") or ""
            yield {
                "product_id": str(p.get("id")),
                "product_name": html.unescape(str(p.get("name") or "")).strip()[:500],
                "category": p.get("category_name"),
                "price": str(price) if price is not None else None,
                "currency": self.currency,
                "available": bool(p.get("is_in_stock", True)),
                "url": f"https://tezeon.com/products/{slug}"
                if slug
                else "https://tezeon.com/grocery",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        next_url = data.get("next")
        if next_url and page < MAX_PAGES:
            yield scrapy.Request(
                next_url,
                callback=self.parse_page,
                meta={"page": page + 1},
            )
