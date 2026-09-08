"""Spider for Marketmeri.com (https://www.marketmeri.com/) -- Papua New
Guinea's leading general classifieds site (est. 2012). Wide COICOP coverage
(coicop_classification: classifier) -- three category landings are crawled:
real-estate/for-rent (COICOP 04.1.1 rentals), vehicles (07.1.1 motor
vehicles), and high-tech (09.1 electronics).

Server-rendered Bootstrap-style HTML, no JS hydration needed -- confirmed
live 2026-09-06 with curl_cffi impersonate=chrome124, no WAF encountered.
Each listing card is a ``div.listing-wrapper-grid`` with a stable shape
across all three categories:

  - PDP url: ``a.target-url::attr(href)``
  - numeric id: ``span.listing-heart::attr(data-id)`` (also the URL's
    trailing numeric suffix)
  - title: ``span.listing-title::text``
  - price: the ``data-price`` attribute on the card's "Contact Seller"
    button is a clean pre-parsed numeric (avoids reparsing "K 950" /
    "K 45,000" text)
  - location: ``span.listing-location::text``

Pagination is ``?page=<n>`` on each category's landing URL; dedup on the
numeric listing id, stop when a page yields zero fresh listings.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_DATA_PRICE_RE = re.compile(r'data-price="([\d.]+)"')

_CATEGORIES = [
    ("https://www.marketmeri.com/real-estate/for-rent", "real-estate-for-rent"),
    ("https://www.marketmeri.com/vehicles", "vehicles"),
    ("https://www.marketmeri.com/high-tech", "high-tech"),
]


class MarketmeriPgSpider(scrapy.Spider):
    name = "marketmeri_pg"
    allowed_domains = ["marketmeri.com", "www.marketmeri.com"]
    currency = "PGK"
    language = "en"
    MAX_PAGES = 60

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        for base_url, label in _CATEGORIES:
            yield scrapy.Request(
                base_url,
                callback=self.parse,
                meta={
                    "impersonate": "chrome124",
                    "page": 1,
                    "base": base_url,
                    "label": label,
                    "seen": set(),
                },
            )

    def parse(self, response):
        base = response.meta["base"]
        page = response.meta["page"]
        label = response.meta["label"]
        seen = response.meta["seen"]

        cards = response.css("div.listing-wrapper-grid")
        fresh = 0
        for card in cards:
            item = self._item(card, label)
            if item is None:
                continue
            pid = item["product_id"]
            if pid in seen:
                continue
            seen.add(pid)
            fresh += 1
            yield item

        self.logger.info(
            "marketmeri_pg: label=%s page=%d cards=%d fresh=%d cumulative=%d",
            label, page, len(cards), fresh, len(seen),
        )

        if fresh and page < self.MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{base}?page={nxt}",
                callback=self.parse,
                meta={
                    "impersonate": "chrome124",
                    "page": nxt,
                    "base": base,
                    "label": label,
                    "seen": seen,
                },
            )

    def _item(self, card, label: str) -> dict | None:
        url = card.css("a.target-url::attr(href)").get()
        pid = card.css("span.listing-heart::attr(data-id)").get()
        title = (card.css("span.listing-title::text").get() or "").strip()
        if not (url and pid and title):
            return None
        html = card.get()
        m = _DATA_PRICE_RE.search(html)
        if not m:
            return None
        price = float(m.group(1))
        if price <= 0:
            return None
        location = (card.css("span.listing-location::text").get() or "").strip() or None
        return {
            "product_id": pid,
            "product_name": title,
            "category": label,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": url,
            "language": self.language,
            "location": location,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
