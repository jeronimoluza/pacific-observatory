"""
Spider for T Market Online (Bulgaria) — https://tmarketonline.bg/.

CloudCart-platform storefront (Maxima-group chain). Category pages are
server-rendered: e.g. /category/svinsko-meso -> 200, real product cards
with prices, re-verified live 2026-08-06.

Currency trap: Bulgaria adopted the euro (Jan 2026). The storefront now
shows EUR as the *primary* displayed price (`bgn2eur-primary-currency`,
e.g. '1,43 €') with BGN as a secondary reference figure
(`bgn2eur-secondary-currency`, '2,80 лв.') -- cfg_currency (BGN) is stale;
we take EUR as the real transactional currency per the probe.

Category discovery: `/sitemap/category/1.xml` lists 187 `/category/<slug>`
URLs, walked in full -- see `_tmarketonline_bg_categories.txt`.

Pagination is `?page=N` (per-page selector confirms up to 96/page, default
48); stop when a page returns zero cards. Note: during manual
re-verification this site returned a transient Cloudflare "Just a moment"
challenge after several rapid unpaced requests, which cleared on its own
after ~20 minutes -- the spider's mandated 2s delay / 1-concurrent settings
are far gentler than that burst, but MAX_PAGES is kept modest as a
precaution.

Product cards: `<h3 class="_product-name-tag"><a href="URL">NAME</a></h3>`
followed by `<span class="bgn2eur-primary-currency">PRICE €</span>`.
"""

import html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://tmarketonline.bg"
_CATEGORY_LIST_PATH = Path(__file__).parent / "_tmarketonline_bg_categories.txt"
_CARD_RE = re.compile(
    r'class="_product-name-tag"><a href="([^"]+)">([^<]+)</a></h3>.*?'
    r'class="bgn2eur-primary-currency">([\d,]+)\s*€',
    re.S,
)
MAX_PAGES = 20  # safety cap


def _load_categories() -> list[str]:
    return [
        line.strip()
        for line in _CATEGORY_LIST_PATH.read_text().splitlines()
        if line.strip()
    ]


class TmarketonlineBgSpider(scrapy.Spider):
    name = "tmarketonline_bg"
    allowed_domains = ["tmarketonline.bg"]
    currency = "EUR"
    language = "bg"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 3.0,
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
                f"{_BASE}/category/{slug}",
                callback=self.parse_category,
                meta={"category": slug, "page": 1},
            )

    def parse_category(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"tmarketonline_bg: {category} page={page} products={len(cards)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for url_path, name, price in cards:
            yield {
                "product_id": url_path.rstrip("/").rsplit("/", 1)[-1],
                "product_name": html.unescape(name).strip()[:500],
                "category": category,
                "price": price.replace(",", "."),
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
                f"{_BASE}/category/{category}?page={next_page}",
                callback=self.parse_category,
                meta={"category": category, "page": next_page},
            )
