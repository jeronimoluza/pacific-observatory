"""
Spider for Edeka24 (Germany) — https://www.edeka24.de/.

OXID eShop storefront (nationwide shipping, shelf-stable assortment only —
no fresh produce/meat/dairy). The homepage's server-rendered nav tree
(`span[data-link]` under `ul.nav-list-main`) exposes the full category
hierarchy; 217 leaf category paths (no deeper children) are listed in
`_edeka24_de_categories.txt` and cover the whole catalog without the
redundant walks of also crawling their parent categories.

Each category page paginates via `?pgNr=N` (0-indexed: the un-suffixed URL
is page 0, `?pgNr=1` is page 1, ...). A `div.product-item` card carries the
product URL + name in `a.title h2` and price in `div.price` (e.g. '3,00 €').

robots.txt declares `Crawl-delay: 20` for `User-agent: *` — DOWNLOAD_DELAY
here is set to 20s accordingly (slower than the wave's usual 2.0s default).

Re-verified live 2026-08-06: /Pralinen/ -> 200, 30 real product cards incl.
'Ferrero Giotto Pastel de Nata 4ST 154G - Abverkauf' 3,00 €; /Pralinen/?pgNr=1
-> 200, 8 more (distinct) cards, confirming real pagination.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.edeka24.de"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_edeka24_de_categories.txt"
_MAX_PAGES = 30  # safety cap per category (pgNr values 0.._MAX_PAGES)
_PRICE_RE = re.compile(r"([0-9]+,[0-9]{2})")


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class Edeka24DeSpider(scrapy.Spider):
    name = "edeka24_de"
    allowed_domains = ["edeka24.de"]
    currency = "EUR"
    language = "de"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 20.0,
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
                callback=self.parse_page,
                meta={"path": path, "pg_nr": 0},
            )

    def parse_page(self, response):
        path = response.meta["path"]
        pg_nr = response.meta["pg_nr"]
        category = path.strip("/").replace("/", " > ")

        cards = response.css("div.product-item")
        logger.info(f"edeka24_de: {path} pgNr={pg_nr} count={len(cards)}")
        if not cards:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            url = card.css("a.title::attr(href)").get()
            name = card.css("a.title h2::text").get()
            price_text = card.css("div.price::text").get()
            if not url or not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            product_id = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".html")
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": m.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if pg_nr < _MAX_PAGES:
            nxt = pg_nr + 1
            yield scrapy.Request(
                f"{_BASE}{path}?pgNr={nxt}",
                callback=self.parse_page,
                meta={"path": path, "pg_nr": nxt},
            )
