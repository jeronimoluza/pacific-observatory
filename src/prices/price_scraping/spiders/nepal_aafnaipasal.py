"""Scrape current grocery cards from Aafnai Pasal Nepal."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.product article"):
        product_id = card.css(".add-to-cart::attr(data-product)").get()
        url = card.css("a.title::attr(href)").get()
        name = " ".join(card.css("a.title::attr(title)").get("").split())
        if not product_id or not url or not name or product_id in seen:
            continue
        direct_text = " ".join(card.css("div.price::text").getall())
        match = re.search(r"\d[\d,]*(?:\.\d+)?", direct_text)
        try:
            price = Decimal(match.group(0).replace(",", "") if match else "")
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
            "currency": "NPR",
            "country": "Nepal",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class NepalAafnaipasalSpider(scrapy.Spider):
    name = "nepal_aafnaipasal"
    allowed_domains = ["aafnaipasal.com", "www.aafnaipasal.com"]
    start_urls = ["https://aafnaipasal.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
