"""
Spider for DoorShoppin (Malawi) — https://doorshoppin.com/.

Custom PHP SSR site (index.php homepage is broken — "Catalog unavailable" —
so we hit the category page directly). category.php?cat_id=Groceries
renders the entire 501-product grocery catalog on a single page (no
pagination needed; the byte count and product-card count both confirm
all 501 are present in one response).

Each `.product-card` carries id/name/price directly as data-* attributes on
its add-to-cart button: `data-id="1038" data-name="Apple Red PP 1kg Bag"
data-price="10899"` (price already in plain MWK, no minor-unit scaling).
"""

import html
import logging
import re
from datetime import datetime, timezone
from typing import Iterator

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://doorshoppin.com/Doorshoppin/category.php?cat_id=Groceries"

_CARD_RE = re.compile(r'data-id="(\d+)"\s+data-name="([^"]*)"\s+data-price="([\d.]+)"')


class DoorshoppinMwSpider(scrapy.Spider):
    name = "doorshoppin_mw"
    allowed_domains = ["doorshoppin.com"]
    currency = "MWK"
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
        yield scrapy.Request(_URL, callback=self.parse_page)

    def parse_page(self, response):
        cards = _CARD_RE.findall(response.text)
        logger.info(f"doorshoppin_mw count={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product_id, name, price in cards:
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": "Groceries",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": f"{_URL}#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

    # ------------------------------------------------------------------
    # Crawl backfiller (prices/backfill.py's parse_html hook). This site has
    # exactly one URL worth archiving (`_URL`, the single page carrying the
    # whole 501-product catalog inline) and no JSON-LD/meta at all -- the
    # live parse's own `_CARD_RE` is the correct and only extraction, reused
    # verbatim against the archived snapshot.
    # ------------------------------------------------------------------
    @classmethod
    def parse_html(cls, html_text: str, url: str) -> Iterator[dict]:
        """Parse one archived DoorShoppin catalog page."""
        for product_id, name, price in _CARD_RE.findall(html_text):
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": "Groceries",
                "price": price,
                "currency": cls.currency,
                "available": True,
                "url": f"{url}#{product_id}",
                "language": cls.language,
            }
