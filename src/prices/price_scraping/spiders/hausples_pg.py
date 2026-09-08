"""Spider for Hausples.com.pg (https://www.hausples.com.pg/) -- Papua New
Guinea's largest real-estate portal (Digital Classifieds Group). Rental
listings only -- COICOP 04.1.1 (actual rentals paid by tenants).

Server-rendered Next.js listing pages carry a full ``__NEXT_DATA__`` JSON
blob with every listing on the page already embedded --
``props.pageProps.cacheData.results.data.results`` -- no per-property PDP
fetch needed. Each entry carries ``id``, ``address``, ``headline``,
``categoryName``, ``url``, and ``displayRent`` (e.g. ``"K5,000"``, or
``"POA"`` -- price on application, dropped). The listing page's own filter
labels confirm rent is quoted **per week** ("Price (per week)", "Median
asking rent per week"), currency PGK (``market.currency.code == "pgk"``).

Pagination is ``/rent/?page=<n>``; ``data.props.pageProps.cacheData.
results.data.lastPage`` gives the true page count (23 pages / 458 listings
at onboarding time, 2026-09-06). Confirmed live with curl_cffi
impersonate=chrome124, no WAF encountered.

Listings with no numeric rent (``displayRent == "POA"``) are dropped.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)
_RENT_RE = re.compile(r"[\d,]+")

_LANDING_URL = "https://www.hausples.com.pg/rent/"


class HausplesPgSpider(scrapy.Spider):
    name = "hausples_pg"
    allowed_domains = ["hausples.com.pg", "www.hausples.com.pg"]
    currency = "PGK"
    language = "en"
    MAX_PAGES = 30  # site reports lastPage=23 at onboarding; margin for growth

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _LANDING_URL,
            callback=self.parse,
            meta={"impersonate": "chrome124", "page": 1, "seen": set()},
        )

    def parse(self, response):
        page = response.meta["page"]
        seen = response.meta["seen"]

        m = _NEXT_DATA_RE.search(response.text)
        if not m:
            logger.warning("hausples_pg: no __NEXT_DATA__ on %s", response.url)
            return
        try:
            data = json.loads(m.group(1))
            rd = data["props"]["pageProps"]["cacheData"]["results"]["data"]
            results = rd["results"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "hausples_pg: could not walk __NEXT_DATA__ on %s: %s", response.url, exc
            )
            return
        last_page = rd.get("lastPage", self.MAX_PAGES)

        fresh = 0
        for listing in results:
            item = self._item(listing)
            if item is None:
                continue
            lid = listing.get("id")
            if lid in seen:
                continue
            seen.add(lid)
            fresh += 1
            yield item

        logger.info(
            "hausples_pg: page=%d fresh=%d cumulative=%d lastPage=%s",
            page, fresh, len(seen), last_page,
        )

        nxt = page + 1
        if fresh and nxt <= min(last_page, self.MAX_PAGES):
            yield scrapy.Request(
                f"{_LANDING_URL}?page={nxt}",
                callback=self.parse,
                meta={"impersonate": "chrome124", "page": nxt, "seen": seen},
            )

    def _item(self, listing: dict) -> dict | None:
        lid = listing.get("id")
        url = listing.get("url")
        headline = listing.get("headline") or listing.get("address")
        display_rent = listing.get("displayRent")
        if not (lid and url and headline and display_rent):
            return None
        m = _RENT_RE.search(display_rent)
        if not m:
            return None
        rent = float(m.group(0).replace(",", ""))
        if rent <= 0:
            return None
        address = listing.get("address")
        category = listing.get("categoryName")
        full_url = url if url.startswith("http") else f"https://www.hausples.com.pg{url}"
        return {
            "product_id": str(lid),
            "product_name": f"{headline} — {address}" if address else headline,
            "category": category,
            "price": rent,
            "currency": self.currency,
            "available": True,
            "url": full_url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
