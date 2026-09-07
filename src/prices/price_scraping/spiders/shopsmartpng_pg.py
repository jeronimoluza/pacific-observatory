"""ShopSmart PNG CS-Cart grocery and beverage category pages."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import scrapy

_BASE = "https://shopsmartpng.com"
_START_URLS = [
    f"{_BASE}/grocery-and-gourmet-food/?items_per_page=96",
    f"{_BASE}/food/?items_per_page=96",
]
_PRICE_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")


class ShopSmartPngPgSpider(scrapy.Spider):
    name = "shopsmartpng_pg"
    allowed_domains = ["shopsmartpng.com"]
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

    async def start(self):
        for url in _START_URLS:
            yield scrapy.Request(url, callback=self.parse_category)

    def parse_category(self, response):
        category = response.url.split("shopsmartpng.com/", 1)[-1].split("/", 1)[0]
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("div.ty-grid-list__item"):
            item = self._item(card, category, scraped_at)
            if item:
                yield item

    def _item(self, card, category: str, scraped_at: str):
        link = card.css("a.product-title")
        href = link.css("::attr(href)").get()
        name = link.css("::attr(title)").get() or link.css("::text").get()
        product_id = card.css('input[name*="[product_id]"]::attr(value)').get()
        price_text = " ".join(card.css(".ty-price-num::text").getall())
        if not href or not name or "contact us for a price" in price_text.lower():
            return None
        match = _PRICE_RE.search(price_text.replace(",", ""))
        if not match:
            return None
        return {
            "product_id": product_id or href.rstrip("/").rsplit("/", 1)[-1],
            "product_name": html.unescape(name).strip()[:500],
            "category": category.replace("-", " "),
            "price": match.group(1),
            "currency": self.currency,
            "available": not bool(card.css(".ty-qty-out-of-stock")),
            "url": href,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
