"""Scrape current marketplace cards from MSSK Chad."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


PRICE_RE = re.compile(r"([0-9][0-9\s\u00a0\u202f,]*)\s*FCFA\b", re.IGNORECASE)


def clean(value):
    return " ".join(unescape(value or "").split())


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css(".ps-product--inner"):
        link = card.css("a.ps-product__title")
        url = link.css("::attr(href)").get()
        name = clean(link.css("::attr(title)").get() or link.xpath("string(.)").get())
        seller = clean(card.css("a.ps-product__vendor::text").get())
        price_text = clean(card.css("p.ps-product__price > span::text").get())
        match = PRICE_RE.search(price_text)
        if not url or not name or not match:
            continue
        product_id = url.rstrip("/").rsplit("/", 1)[-1]
        if product_id in seen:
            continue
        try:
            price = Decimal(re.sub(r"[\s,]", "", match.group(1)))
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        attributed_name = f"{name} - {seller}" if seller else name
        yield {
            "product_id": product_id,
            "product_name": attributed_name[:500],
            "category": "marketplace consumer goods",
            "price": format(price, "f"),
            "currency": "XAF",
            "country": "Chad",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "fr",
            "scraped_at_utc": scraped_at,
        }


class ChadMsskSpider(scrapy.Spider):
    name = "chad_mssk"
    allowed_domains = ["mssk.app", "www.mssk.app"]
    start_urls = ["https://www.mssk.app/"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        yield from parse_cards(response)
