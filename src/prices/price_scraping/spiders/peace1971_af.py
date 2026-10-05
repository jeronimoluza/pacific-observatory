"""Scrape current stationery cards from Peace Stationery Afghanistan."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


PRICE_RE = re.compile(r"\bAFN\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b", re.IGNORECASE)


def parse_cards(response):
    seen = set()
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in response.css("div.card-product"):
        product_id = card.css("a.btn-main-product::attr(data-id)").get()
        link = card.css("div.card-product-info a.title.link")
        url = link.css("::attr(href)").get()
        name = " ".join(unescape(link.xpath("string(.)").get() or "").split())
        price_text = " ".join(card.css("span.price::text").getall())
        match = PRICE_RE.search(price_text)
        if not product_id or not name or not url or not match or product_id in seen:
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
            "category": "stationery",
            "price": format(price, "f"),
            "currency": "AFN",
            "country": "Afghanistan",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class Peace1971AfSpider(scrapy.Spider):
    name = "peace1971_af"
    allowed_domains = ["peace1971.com"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }
    start_urls = ["https://peace1971.com/"]

    def parse(self, response):
        yield from parse_cards(response)
