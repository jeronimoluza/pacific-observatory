"""
Spider for Maxi E-Shop (Kosovo) — https://maxiks.shop/.

Custom PHP storefront (Prishtina supermarket chain, 18 outlets). The full
catalog is server-rendered at /products?page=N (no category filter needed —
pagination alone walks the whole assortment). Each `div.product-card`
carries a product detail link (`a[href*="/product/"]`), name
(`h3.product-title`), and price (`h4.product-price`, e.g. '2.09€').

Re-verified live 2026-08-06: /products -> 200, 20 items/page; /products?page=97
-> 200, 7 items (last partial page); /products?page=98 -> 200, 0 items —
confirms the catalog plateaus at 97 pages.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://maxiks.shop"
_MAX_PAGES = 150  # safety cap; catalog observed to end at page 97
_PRICE_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)")


class MaxiksKsSpider(scrapy.Spider):
    name = "maxiks_ks"
    allowed_domains = ["maxiks.shop"]
    currency = "EUR"
    language = "sq"

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
            f"{_BASE}/products?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        cards = response.css("div.product-card")
        logger.info(f"maxiks_ks: page={page} count={len(cards)}")
        if not cards:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            url = card.css('a[href*="/product/"]::attr(href)').get()
            name = card.css("h3.product-title a::text").get()
            price_text = card.css("h4.product-price::text").get()
            category = card.css('a[href*="?category="]::text').get()
            if not url or not name or not price_text:
                continue
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            product_id = url.rstrip("/").rsplit("/", 1)[-1]
            yield {
                "product_id": product_id,
                "product_name": html.unescape(name).strip()[:500],
                "category": (category or "").strip() or None,
                "price": m.group(1).replace(",", "."),
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }

        if page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}/products?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )
