"""Scrape current cards from Berry Collection Maldives."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


PRICE_RE = re.compile(r"\bMVR\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b", re.IGNORECASE)
ID_RE = re.compile(r"\bpost-(\d+)\b")


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    for card in response.css("li.type-product"):
        classes = card.attrib.get("class", "")
        id_match = ID_RE.search(classes)
        link = card.css("div.title-column h3 a")
        url = link.css("::attr(href)").get()
        name = " ".join((link.xpath("string(.)").get() or "").split())
        price = card.css("span.price")
        text = price.css("ins bdi").xpath("string(.)").get()
        if not text:
            text = price.css("bdi").xpath("string(.)").get()
        price_match = PRICE_RE.search(" ".join((text or "").split()))
        if not id_match or not name or not url or not price_match:
            continue
        try:
            value = Decimal(price_match.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        if value <= 0:
            continue
        yield {
            "product_id": id_match.group(1),
            "product_name": name[:500],
            "category": None,
            "price": format(value, "f"),
            "currency": "MVR",
            "country": "Maldives",
            "sector": "consumer_goods",
            "available": "outofstock" not in classes,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class MaldivesBerrycollectionSpider(scrapy.Spider):
    name = "maldives_berrycollection"
    allowed_domains = ["berrycollection.com"]
    start_urls = ["https://berrycollection.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_cards(response)
