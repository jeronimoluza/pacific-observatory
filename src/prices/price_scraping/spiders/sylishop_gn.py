"""Sylishop Guinea tangible-goods catalogue; explicitly excludes Services."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import scrapy

_ROOT_URL = "https://www.sylishop.com/"
_PRICE_RE = re.compile(r"([0-9][0-9\s,.]*)")
_SERVICE_RE = re.compile(r"\bservices?\b", re.I)


def _clean(value: object) -> str:
    if isinstance(value, (list, tuple)):
        value = " ".join(map(str, value))
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _price(value: object) -> str | None:
    match = _PRICE_RE.search(_clean(value))
    if not match:
        return None
    raw = match.group(1).replace(" ", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        return None
    return f"{amount:.2f}" if amount > 0 else None


class SylishopGnSpider(scrapy.Spider):
    name = "sylishop_gn"
    allowed_domains = ["www.sylishop.com", "sylishop.com"]
    currency = "GNF"
    language = "fr"
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2, "DOWNLOAD_DELAY": 0.25}

    async def start(self):
        yield scrapy.Request(_ROOT_URL, callback=self.parse_catalogue)

    def parse_catalogue(self, response):
        for card in response.css(".product-card, .product-item, [data-product-id]"):
            category = _clean(card.attrib.get("data-category")) or _clean(
                card.css(".product-category ::text, .category ::text, [data-category]::attr(data-category)").getall()
            )
            # This is a hard eligibility rule, not a downstream classification hint.
            if _SERVICE_RE.search(category):
                continue
            name = _clean(card.css(".product-name ::text, .product-title ::text, h2 ::text, h3 ::text").getall())
            price = _price(card.css(".product-price ::text, .price ::text, [itemprop='price']::attr(content)").getall())
            if not name or not price:
                continue
            href = card.css("a[href*='product']::attr(href), a[href]::attr(href)").get()
            product_id = card.attrib.get("data-product-id") or (href.rstrip("/").rsplit("/", 1)[-1] if href else name)
            merchant = _clean(card.css(".merchant ::text, .seller ::text, .store-name ::text").getall()) or None
            description = _clean(card.css(".description ::text, .product-description ::text").getall()) or None
            unit = _clean(card.css(".unit ::text, .packaging ::text").getall()) or None
            yield {
                "product_id": product_id, "product_name": name[:500], "category": category or None,
                "description": description, "merchant": merchant, "unit": unit,
                "price": price, "currency": self.currency, "available": True,
                "locality": "Conakry", "url": response.urljoin(href).split("?", 1)[0] if href else response.url,
                "language": self.language, "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        # Pagination is followed only when Sylishop exposes an explicit next control.
        next_href = response.css("a.next::attr(href), .pagination a[rel='next']::attr(href)").get()
        if next_href:
            yield response.follow(next_href, self.parse_catalogue)
