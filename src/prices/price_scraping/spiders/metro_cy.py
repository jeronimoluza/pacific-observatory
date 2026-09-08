"""
Spider for Metro Supermarkets (Cyprus) — https://www.metro.com.cy/.

Metro Cyprus runs no online store (homepage carries only a physical store
locator, `/gr/stores`) but publishes a weekly "current offers" leaflet page
server-rendered in full on a single URL, with all categories' items present
in the HTML at once (client-side JS only filters by category tab, it does
not lazy-load): `/gr/current_offers`.

Each item:

    <div class="product_item <CATEGORY> <BRAND...>">
      <img class="product_img" src=".../leaflet/<numeric_id>.webp">
      <div class="price_now"><p>&euro;PRICE</p></div>
      <h5 class="item_offer_title">NAME</h5>
    </div>

`product_item`'s class attribute is `"<CATEGORY> <rest of the brand/name
tokens>"` (space-separated, first token is the category, e.g. FRESHMEAT,
MILK); the numeric id embedded in the leaflet image URL is the only stable
per-item identifier available and is used as `product_id`.

Re-verified live 2026-09-06: GET -> 200, 1.4MB, 943 `product_item` blocks
across all 46 category tabs, e.g. "Olympos Milk 3.7% Epilegmenes Farmes
1L" EUR 1.70 (was EUR 1.90).

Gotcha: since every item comes off the same single page, `url` is given a
`#<id>` fragment per item -- `DuplicationPipeline` dedups on
`item["url"]`, so leaving every row pointed at the bare page URL collapsed
943 items down to 1 kept row on first test.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://www.metro.com.cy/gr/current_offers"
_SPLIT = '<div class="product_item '
_CATEGORY_RE = re.compile(r'^([A-Z0-9]+)')
_ID_RE = re.compile(r"leaflet/(\d+)\.webp")
_PRICE_RE = re.compile(r'price_now\s*"[^>]*>\s*<p>[^0-9]*([0-9]+[.,][0-9]{2})')
_TITLE_RE = re.compile(r'item_offer_title">([^<]+)</h5>')


class MetroCySpider(scrapy.Spider):
    name = "metro_cy"
    allowed_domains = ["metro.com.cy"]
    currency = "EUR"
    language = "el"

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
        yield scrapy.Request(_URL, callback=self.parse_offers)

    def parse_offers(self, response):
        # Split on the repeating block marker rather than one big regex --
        # a single greedy/non-greedy regex across the 1.4MB page risks
        # catastrophic backtracking.
        blocks = response.text.split(_SPLIT)[1:]
        logger.info(f"metro_cy: {len(blocks)} offer items")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for block in blocks:
            cat_m = _CATEGORY_RE.match(block)
            id_m = _ID_RE.search(block)
            price_m = _PRICE_RE.search(block)
            title_m = _TITLE_RE.search(block)
            if not (id_m and price_m and title_m):
                continue
            price_clean = price_m.group(1).replace(",", ".").strip()
            yield {
                "product_id": id_m.group(1),
                "product_name": title_m.group(1).strip()[:500],
                "category": cat_m.group(1) if cat_m else None,
                "price": price_clean,
                "currency": self.currency,
                "available": True,
                "url": f"{_URL}#{id_m.group(1)}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
