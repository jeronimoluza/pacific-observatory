"""Canoe House Palau restaurant menu prices."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy


_PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]{1,2})?)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-")


class CanoeHousePalauSpider(scrapy.Spider):
    name = "canoehouse_palau"
    allowed_domains = ["canoehousepalau.com", "www.canoehousepalau.com"]
    start_urls = ["https://canoehousepalau.com/"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
    }

    _META = {"impersonate_args": {"verify": False}}

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, meta=self._META)

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        seen = set()
        for block in response.css(".menus"):
            name = _clean(block.css("h3::text").get())
            if not name:
                continue
            description = _clean(
                " ".join(block.css(".text p ::text, .text p::text").getall())
            )
            for price_node in block.css(".price"):
                price_text = _clean(" ".join(price_node.css("::text").getall()))
                price_match = _PRICE_RE.search(price_text)
                if not price_match:
                    continue
                variant = _clean(_PRICE_RE.sub("", price_text))
                product_name = f"Canoe House {name}"
                if variant:
                    product_name = f"{product_name} ({variant})"
                product_id = _slug(product_name)
                if product_id in seen:
                    continue
                seen.add(product_id)
                yield {
                    "product_id": product_id,
                    "product_name": product_name[:500],
                    "category": "Restaurant menu item",
                    "price": price_match.group(1),
                    "price_text": price_text,
                    "currency": self.currency,
                    "available": True,
                    "unit": variant or "menu item",
                    "description": description or None,
                    "url": f"{response.url}#{product_id}",
                    "language": self.language,
                    "scraped_at_utc": scraped_at,
                }
