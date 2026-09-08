"""
Spider for Unegui.mn (https://www.unegui.mn/) — Mongolia's largest classifieds
marketplace.

Re-probed 2026-09-06 after a stale `known_blockers.md` verdict ("HTTP 403
from non-Mongolian IP; likely an application-tier IP allowlist"). That
verdict does not hold from this network: curl_cffi impersonation (chrome124)
gets a clean 200 on both the homepage and the /avto-mashin/ (vehicles)
listing, with no allowlist behaviour observed. The front end is a Vue/Nuxt
SPA, but each listing page embeds the full result set as an escaped JSON
string inside the page's initial-state payload — no separate API call is
needed. Confirmed real pagination: page 1 and page 2 of /avto-mashin/ return
60 listings each with zero id overlap.

Scoped to the /avto-mashin/ (vehicle classifieds) category only — narrow
COICOP 07.1 (purchase of vehicles). Unegui.mn also carries real-estate,
electronics, and general-goods classifieds sections; those are out of scope
for this spider (used-goods classifieds pricing is a different analytical
shape from a retail catalogue and would need its own COICOP scoping pass).

Listing page family only (no per-ad PDP fetch needed — price, title, and id
are all present in the listing payload).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.unegui.mn/avto-mashin/"
_PAGE_CAP = 300  # observed max page ~292 at probe time

# The listing payload is embedded as a backslash-escaped JSON string inside
# the page HTML (Nuxt initial-state serialization), so the delimiters below
# match literal `\"` sequences, not raw JSON quotes.
_LISTING_RE = re.compile(
    r'\\"id\\":(\d+),\\"title\\":\\"([^\\]*?)\\",\\"description\\":\\"[^\\]*?\\",'
    r'\\"price\\":\\"[^\\]*?\\".*?\\"price_without_currency\\":\\"(\d*)\\".*?'
    r'\\"url\\":\\"([^\\]+?)\\"'
)


class UneguiMnSpider(scrapy.Spider):
    name = "unegui_mn"
    allowed_domains = ["unegui.mn"]
    currency = "MNT"
    language = "mn"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_BASE, callback=self.parse_listing, meta={"page": 1})

    def parse_listing(self, response):
        page = response.meta["page"]
        rows = _LISTING_RE.findall(response.text)
        logger.info("unegui_mn: page %d -> %d listings", page, len(rows))

        for ad_id, title, price_raw, url in rows:
            if not price_raw or int(price_raw) <= 0:
                continue
            yield {
                "product_id": ad_id,
                "product_name": title.strip()[:500],
                "category": "avto-mashin",
                "price": price_raw,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(url),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        if rows and page < _PAGE_CAP:
            next_page = page + 1
            yield scrapy.Request(
                f"{_BASE}?page={next_page}",
                callback=self.parse_listing,
                meta={"page": next_page},
            )
