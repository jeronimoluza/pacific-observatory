"""
Spider for HyperSale (Sudan) — https://www.hypersale.sd/.

Laravel/6valley-theme SSR HTML. The grocery vertical is a dedicated category
page at /category/hypersale-super-market (distinct from the site's general
marketplace, which also carries electronics/fashion/beauty). Standard
?page=N pagination advances the grid (27 pages observed live).

Each product card (div.aiz-card-box) carries the price span before the name
link in document order: `class="fw-700 text-primary">24.000SDG</span>` ...
`<a href="https://www.hypersale.sd/product/<slug>" class="d-block text-reset">
<name></a>`. Product names are predominantly Arabic.

GOTCHA: prices render like "24.000SDG" and also bare "800SDG" with no
separator at all — confirms '.' is a thousands separator here (European/PHP
number_format convention), not a decimal point. We strip '.' before storing.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.hypersale.sd"
_CATEGORY_PATH = "/category/hypersale-super-market"
MAX_PAGES = 50

_CARD_RE = re.compile(
    r'class="fw-700 text-primary">([^<]+)</span>.*?'
    r'<a href="(https://www\.hypersale\.sd/product/[^"]+)" class="d-block text-reset">([^<]*)</a>',
    re.S,
)


def _parse_price(raw: str) -> str:
    digits = raw.replace("SDG", "").strip()
    digits = digits.replace(".", "")
    return digits


class HypersaleSdSpider(scrapy.Spider):
    name = "hypersale_sd"
    allowed_domains = ["hypersale.sd"]
    currency = "SDG"
    language = "ar"

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
            f"{_BASE}{_CATEGORY_PATH}",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = _CARD_RE.findall(response.text)
        logger.info(f"hypersale_sd page={page} count={len(cards)}")
        if not cards:
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for raw_price, url, name in cards:
            yield {
                "product_id": url.rstrip("/").rsplit("/", 1)[-1],
                "product_name": html.unescape(name).strip()[:500],
                "category": None,
                "price": _parse_price(raw_price),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        if page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}{_CATEGORY_PATH}?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
