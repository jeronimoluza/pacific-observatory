"""Spider for MilanWholesale (Nepal) — https://www.milanwholesale.com/.

Server-rendered HTML (bespoke PHP app; wp-json/wc endpoints 404, so not
WordPress despite the storefront look). Re-verified live 2026-08-06:
GET /product-category/rice -> 301 to https://www.milanwholesale.com/... ->
200, 104587 bytes SSR HTML with real product cards, e.g. 'Rajhans Royal
Pulao Basmati Rice 20kg' Rs.3400. Category nav on the homepage exposes 17
`/product-category/<slug>` URLs, listed in `_milanwholesale_np_categories.txt`
(precedent: `_glomark_lk_categories.txt` + `glomark_lk.py`). Each category
paginates via `?page=N` (confirmed `page=2`/`page=3` links present); we walk
pages until a page returns zero product cards.

Wholesale bulk pricing on dry staples only (rice, dal/pulses, oil/ghee,
spices, sugar/salt, dry fruits, noodles, biscuits) — no fresh produce, dairy,
or meat. Currency NPR (matches countries.yaml).
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.milanwholesale.com"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_milanwholesale_np_categories.txt"
_MAX_PAGES = 30  # safety cap per category
_CARD_RE = re.compile(
    r'<h3><a href="(/product/[^"]+)">([^<]*)</a></h3>.*?'
    r'class="final-price">Rs\.?\s*([0-9,]+\.?[0-9]*)</span>',
    re.S,
)


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class MilanwholesaleNpSpider(scrapy.Spider):
    name = "milanwholesale_np"
    allowed_domains = ["milanwholesale.com", "www.milanwholesale.com"]
    currency = "NPR"
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
                meta={"category_path": path, "page": 1},
            )

    def parse_category(self, response):
        category = response.meta["category_path"].rsplit("/", 1)[-1]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"milanwholesale_np: {category} page={page} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            yield {
                "product_id": url_path.rsplit("/", 1)[-1],
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price.replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}{url_path}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if cards and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}{response.meta['category_path']}?page={nxt}",
                callback=self.parse_category,
                meta={"category_path": response.meta["category_path"], "page": nxt},
            )
