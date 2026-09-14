"""Scrape current consumer-product cards from SmartGau Nepal."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import scrapy


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.product-card"):
        url = card.css("h6.pc__title a::attr(href)").get()
        name = " ".join(card.css("h6.pc__title a::text").get("").split())
        product_id = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] if url else ""
        prices = card.css("span.price-sale::text").getall()
        if not product_id or not name or not prices or product_id in seen:
            continue
        match = re.search(r"\d[\d,]*(?:\.\d+)?", prices[-1])
        amount = match.group(0).replace(",", "") if match else ""
        try:
            price = Decimal(amount)
        except (InvalidOperation, TypeError):
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        category = " ".join(card.css("p.pc__category::text").get("").split())
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category or None,
            "price": format(price, "f"),
            "currency": "NPR",
            "country": "Nepal",
            "sector": "consumer_goods",
            "available": "Out of Stock" not in " ".join(card.css("::text").getall()),
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class NepalSmartgauSpider(scrapy.Spider):
    name = "nepal_smartgau"
    allowed_domains = ["smartgau.com", "www.smartgau.com"]
    start_urls = ["https://smartgau.com/shop"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
