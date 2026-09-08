"""
Spider for tmcars.info — Turkmenistan vehicle classifieds marketplace.

Verified live 2026-09-06: Next.js (App Router / RSC) site, fully
server-rendered — curl_cffi chrome124 with no headers returns the complete
card grid in the initial HTML, no JS execution required. Listing cards
follow a stable text pattern:
  `text-text-secondary mb-2 truncate text-sm font-bold">{PRICE} TMT</div>
   <a class="group" href="/cars/{id}/{slug}"><p ...>{TITLE}</p>`
extracted below via a plain regex rather than a CSS selector — the class
names are Tailwind utility soup with no stable hook, but the price->link->
title ordering is consistent across every sampled card.

No working query-string pagination was found: `?page=2`, `?p=2`,
`?offset=100`, `?skip=100`, `?pageNumber=2` all return the same first page
of ~100 listings (deeper pages are presumably loaded via an internal RSC
fetch triggered by scroll, not a plain query param). The spider therefore
walks a small fixed set of listing pages — `/cars/all` (general, ~100
items, mixes passenger cars with trucks/construction equipment e.g.
"Kamaz 6520", "Liugong 835n") and `/cars/all/spestehnika` (special
equipment) — rather than a real paginated crawl. Each item already has a
distinct per-listing URL (`/cars/{id}/{slug}`), so DuplicationPipeline's
URL-based dedup does not collapse these into one row even though the
catalog itself doesn't paginate.

Prices are plain TMT integers with "." as a thousands separator (e.g.
"225.000 TMT" = 225,000 manat) — stripped of dots before emitting.

coicop_classification left as classifier (not narrowed to 07.1.1 motor
cars): the catalog mixes passenger vehicles with commercial trucks and
heavy equipment, which are not all the same COICOP class. channel:
marketplace (seller-authored listing titles).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_LISTING_PATHS = ["/cars/all", "/cars/all/spestehnika"]

_CARD_RE = re.compile(
    r'text-text-secondary mb-2 truncate text-sm font-bold">([\d.,]+)\s*TMT</div>'
    r'<a class="group" href="(/cars/\d+/[^"]+)"><p[^>]*>([^<]+)</p>',
)


class TmcarsTmSpider(scrapy.Spider):
    name = "tmcars_tm"
    allowed_domains = ["tmcars.info"]
    base_url = "https://tmcars.info"
    currency = "TMT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for path in _LISTING_PATHS:
            yield scrapy.Request(
                f"{self.base_url}{path}",
                callback=self.parse_listing,
                meta={"path": path},
            )

    def parse_listing(self, response):
        path = response.meta["path"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for price_raw, href, title in _CARD_RE.findall(response.text):
            price_clean = price_raw.replace(".", "").replace(",", "")
            try:
                price_val = float(price_clean)
            except ValueError:
                continue
            if price_val <= 0:
                continue
            n += 1
            car_id = href.split("/")[2]
            yield {
                "product_id": car_id,
                "product_name": title.strip()[:500],
                "category": path.rsplit("/", 1)[-1] if "/" in path else None,
                "price": str(price_val),
                "currency": self.currency,
                "available": True,
                "url": f"{self.base_url}{href}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: path={path} items={n}")
