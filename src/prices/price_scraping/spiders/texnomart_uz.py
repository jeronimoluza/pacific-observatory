"""texnomart.uz — Uzbekistan electronics/appliances retailer.

Verified live 2026-08-17. The homepage itself is a Nuxt client-rendered
shell (the payload is a devalue-style minified JS blob, not usable as a data
source), and the ``api.texnomart.uz`` subdomain referenced in that blob does
not resolve from here. Category *listing* pages
(``https://texnomart.uz/katalog/<slug>/``) are, however, properly
server-rendered with real product cards, and accept ``?page=<N>`` (verified:
page 2 returns a disjoint product set from page 1). Each listing page prints
an exact "1 - 20 of 98 items" counter (``div.pagination``), which this
spider parses to compute the exact page count per category rather than
guessing a cap. Product cards are ``div.product-item-wrapper`` with a
``data-ga-id`` id on the ancestor grid column; name from
``a.product-name h2``; price from ``div.product-price__current`` (plain
digits + "so'm", no thousands-separator ambiguity).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_HREF_RE = re.compile(r'href="(/katalog/[a-z0-9_-]+/)"')
_PRICE_NUM_RE = re.compile(r"[\d\s]+")
_OF_ITEMS_RE = re.compile(r"of\s+(\d+)\s+items")

_PAGE_SIZE = 20
_MAX_PAGES_PER_CATEGORY = 10


class TexnomartUzSpider(scrapy.Spider):
    name = "texnomart_uz"
    allowed_domains = ["texnomart.uz"]
    currency = "UZS"
    language = "uz"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.4,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            "https://texnomart.uz/katalog/", callback=self.parse_katalog
        )

    def parse_katalog(self, response):
        slugs = sorted(set(_CATEGORY_HREF_RE.findall(response.text)))
        logger.info("texnomart_uz: %d category paths discovered", len(slugs))
        for path in slugs:
            if path == "/katalog/":
                continue
            yield scrapy.Request(
                urljoin(response.url, path),
                callback=self.parse_category,
                meta={"page": 1, "path": path},
            )

    def parse_category(self, response):
        cards = response.css("div.product-item-wrapper")
        scraped_at = datetime.now(timezone.utc).isoformat()
        category = " ".join(
            t.strip() for t in response.css("h1 ::text").getall() if t.strip()
        )
        category = category or None
        emitted = 0
        for card in cards:
            item = self._parse_card(card, response, category, scraped_at)
            if item is not None:
                yield item
                emitted += 1

        page = response.meta["page"]
        path = response.meta["path"]
        logger.info(
            "texnomart_uz: path=%s page=%s cards=%d items=%d",
            path,
            page,
            len(cards),
            emitted,
        )

        if not cards:
            return
        total_pages = self._total_pages(response)
        max_page = min(total_pages, _MAX_PAGES_PER_CATEGORY)
        if page < max_page:
            nxt = page + 1
            yield scrapy.Request(
                f"{urljoin(response.url, path)}?page={nxt}",
                callback=self.parse_category,
                meta={"page": nxt, "path": path},
            )

    @staticmethod
    def _total_pages(response) -> int:
        text = " ".join(response.css("div.pagination ::text").getall())
        m = _OF_ITEMS_RE.search(text)
        if not m:
            return 1
        total_items = int(m.group(1))
        return max(1, -(-total_items // _PAGE_SIZE))

    def _parse_card(self, card, response, category, scraped_at: str) -> dict | None:
        col = card.xpath("ancestor::*[@data-ga-id][1]")
        product_id = col.attrib.get("data-ga-id") if col else None

        a = card.css("a.product-name")
        href = a.attrib.get("href")
        title = a.css("h2::text").get()
        if not product_id or not href or not title or not title.strip():
            return None
        title = title.strip()

        price_text = " ".join(card.css("div.product-price__current ::text").getall())
        price = self._normalize_price(price_text)
        if price is None:
            return None

        return {
            "product_id": product_id,
            "product_name": title[:500],
            "category": category,
            "price": price,
            "currency": self.currency,
            "available": True,
            "url": urljoin(response.url, href),
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    @staticmethod
    def _normalize_price(text: str) -> str | None:
        if not text:
            return None
        m = _PRICE_NUM_RE.search(text.replace("\xa0", " "))
        if not m:
            return None
        s = m.group(0).replace(" ", "").strip()
        if not s:
            return None
        try:
            float(s)
        except ValueError:
            return None
        return s
