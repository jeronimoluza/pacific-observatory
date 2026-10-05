"""Scrape current cards from MtoZero Store Sudan."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


PRICE_RE = re.compile(r"Price:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*SDG\b", re.IGNORECASE)


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("#productsGrid > div.group"):
        link = card.css("a.js-open-product[data-product-id]")
        product_id = (link.css("::attr(data-product-id)").get() or "").strip()
        url = link.css("::attr(href)").get()
        name = " ".join(link[-1:].xpath("string(.)").get(default="").split())
        text = " ".join(card.xpath("string(.)").get(default="").split())
        match = PRICE_RE.search(text)
        if not product_id or not url or not name or not match or product_id in seen:
            continue
        try:
            price = Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": format(price, "f"),
            "currency": "SDG",
            "country": "Sudan",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "ar",
            "scraped_at_utc": scraped_at,
        }


class SudanMtozeroSpider(scrapy.Spider):
    name = "sudan_mtozero"
    allowed_domains = ["store.mtozero.com"]
    start_urls = ["https://store.mtozero.com/?lang=en"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_cards(response)
