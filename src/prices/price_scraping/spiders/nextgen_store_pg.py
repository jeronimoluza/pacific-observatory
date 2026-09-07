"""Nextgen Store PNG HTML catalog for office technology and electronics."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy

_BASE = "https://store.nextgenpng.net"
_START_URLS = [
    f"{_BASE}/shop",
    f"{_BASE}/shop/category/computers-accessories",
    f"{_BASE}/shop/category/printers-consumables",
    f"{_BASE}/shop/category/power-ups",
    f"{_BASE}/shop/category/security-surveillance",
    f"{_BASE}/shop/category/network-items",
]
_PRICE_RE = re.compile(r"K\s*([0-9][0-9,]*(?:\.[0-9]+)?)")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


class NextgenStorePgSpider(scrapy.Spider):
    name = "nextgen_store_pg"
    allowed_domains = ["store.nextgenpng.net"]
    currency = "PGK"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen_urls: set[str] = set()

    async def start(self):
        for url in _START_URLS:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("div.product-card"):
            item = self._item(card, response, scraped_at)
            if item:
                yield item

    def _item(self, card, response, scraped_at: str):
        href = card.css('a[href*="/shop/product/"]::attr(href)').get()
        name = _clean(card.css("h3::text").get())
        product_id = card.css('input[name="product_id"]::attr(value)').get()
        if not href or not name:
            return None

        url = response.urljoin(href)
        if url in self._seen_urls:
            return None
        self._seen_urls.add(url)

        price_match = _PRICE_RE.search(" ".join(card.css("::text").getall()))
        if not price_match:
            return None

        category = _clean(card.css('a[href*="/shop/category/"]::text').get())
        available_text = " ".join(card.css("::text").getall()).lower()
        return {
            "product_id": product_id or url.rstrip("/").rsplit("/", 1)[-1],
            "product_name": html.unescape(name)[:500],
            "category": category or None,
            "price": price_match.group(1).replace(",", ""),
            "currency": self.currency,
            "available": "in stock" in available_text,
            "url": url,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
