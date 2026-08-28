"""
Spider for Magnit.tj (Tajikistan) — https://magnit.tj/.

Custom PHP-style storefront (Dushanbe online supermarket, free home delivery).
Server-rendered category pages at https://magnit.tj/category?id=<n>&page=<n>
carry product name (`.productItemTitle`) and price (`.productPrice` /
`.productItemCurrentPrice`) directly in the raw HTML, with a link to the
product detail page at /product/show/<id>. The homepage nav exposes 164
category ids covering the full assortment (dairy, meat, bakery, drinks,
household, etc.); ids are listed in `_magnit_tj_categories.txt`. Each
category page also renders its own name in `<h1 class="title">`, so we don't
need to hardcode category names alongside the ids.

Re-verified live 2026-08-06: /category?id=3 -> 200, 151KB, 36 real product
cards incl. 'Йогурт Epica® клубника 4.8% 130 г' 24.50 сом (id=3 dairy
category paginates 5 pages per nav links `&page=2..5`). Prices in raw HTML,
e.g. 'Банан...39.90 сом.' — TJS per shard/cfg currency.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://magnit.tj"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_magnit_tj_categories.txt"
_MAX_PAGES = 60  # safety cap per category

_TITLE_RE = re.compile(r'productItemTitle"[^>]*>\s*(?:<a[^>]*>)?\s*([^<]{2,200})')
_PRICE_RE = re.compile(
    r'productItemCurrentPrice">([0-9]+(?:[.,][0-9]+)?)|productPrice">([0-9]+(?:[.,][0-9]+)?)'
)
_ID_RE = re.compile(r"/product/show/(\d+)")


def _load_category_ids() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class MagnitTjSpider(scrapy.Spider):
    name = "magnit_tj"
    allowed_domains = ["magnit.tj"]
    currency = "TJS"
    language = "ru"

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
        for cid in _load_category_ids():
            yield scrapy.Request(
                f"{_BASE}/category?id={cid}&page=1",
                callback=self.parse_category,
                meta={"cid": cid, "page": 1},
            )

    def parse_category(self, response):
        cid = response.meta["cid"]
        page = response.meta["page"]
        h1 = response.css("h1.title::text").get()
        category = (h1 or "").strip() or None

        ids = _ID_RE.findall(response.text)
        titles = _TITLE_RE.findall(response.text)
        raw_prices = _PRICE_RE.findall(response.text)
        prices = [next(g for g in pair if g) for pair in raw_prices if any(pair)]

        n = min(len(ids), len(titles), len(prices))
        logger.info(f"magnit_tj: cid={cid} page={page} products={n}")
        if n == 0:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for i in range(n):
            yield {
                "product_id": ids[i],
                "product_name": html.unescape(titles[i]).strip()[:500],
                "category": category,
                "price": prices[i].replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/product/show/{ids[i]}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/category?id={cid}&page={nxt}",
                callback=self.parse_category,
                meta={"cid": cid, "page": nxt},
            )
