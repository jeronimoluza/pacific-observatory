"""
Spider for tayara.tn — Tunisia classifieds marketplace (Next.js).

Verified live 2026-08-17: /annonces redirects (308) to /annonces/, which
itself resolves to a client-only 404 shell with no listing data. The real
listings live at /ads/?page=N (also mirrored at /listing/?page=N): each
response embeds a `<script id="__NEXT_DATA__">` JSON blob at
props.pageProps.searchedListingsAction with `newHits` (~30/page) +
`premiumHits` + `totalHitsCount` (49,850 nationwide at time of writing).
Confirmed real TND prices, e.g. price:280 (a 280DT land-sale ad),
price:120000 (an apartment). By volume this feed is dominated by
"immobilier" (real estate) and "vehicules" (vehicles) listings, consistent
with a nationwide general classifieds site.

Some hits carry price:0 — "contact for price"/negotiable listings and
promotional "boost my ad" posts, not real prices — dropped rather than
emitted as a fake 0.

Requires ordinary browser Accept/Accept-Language/Referer headers — a bare
curl -A UA only gets a silently truncated response body (content-length
matches what's sent, but the JSON is cut off mid-string with no closing
tags); adding Accept/Accept-Language/Referer resolves it, no TLS/UA
impersonation needed.

Pagination via ?page=N is capped at MAX_PAGES (the full catalog is
~1,662 pages; a full crawl would badly exceed the run budget).
"""

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.tayara.tn/ads/"
MAX_PAGES = 150
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class TayaraTnSpider(scrapy.Spider):
    name = "tayara_tn"
    allowed_domains = ["tayara.tn"]
    currency = "TND"
    language = "fr"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-TN,fr;q=0.9,en;q=0.8",
            "Referer": "https://www.tayara.tn/",
        },
    }

    async def start(self):
        for page in range(1, MAX_PAGES + 1):
            yield scrapy.Request(
                f"{_BASE}?page={page}",
                callback=self.parse_listing,
                meta={"page": page},
            )

    def parse_listing(self, response):
        page = response.meta["page"]
        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("tayara_tn: no __NEXT_DATA__ on page=%s", page)
            return
        try:
            data = json.loads(m.group(1))
        except (ValueError, TypeError):
            logger.warning("tayara_tn: bad JSON on page=%s", page)
            return

        action = (
            data.get("props", {}).get("pageProps", {}).get("searchedListingsAction", {})
        )
        hits = (action.get("newHits") or []) + (action.get("premiumHits") or [])
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for hit in hits:
            title = hit.get("title")
            price = hit.get("price")
            hit_id = hit.get("id")
            if not title or price in (None, "") or float(price) <= 0:
                continue
            n += 1
            metadata = hit.get("metadata") or {}
            yield {
                "product_id": hit_id,
                "product_name": str(title).strip()[:500],
                "category": metadata.get("subCategory"),
                "price": str(price),
                "currency": self.currency,
                "available": True,
                "url": f"https://www.tayara.tn/item/{hit_id}/",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: page={page} hits={n}")
