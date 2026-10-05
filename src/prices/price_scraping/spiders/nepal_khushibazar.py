"""Scrape current stationery offers from Khushi Bazar Nepal."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import scrapy


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.item.grid-view"):
        product_id = card.css("button.add-to-cart1::attr(data-product-id)").get()
        url = card.css('a[href*="/products/"]::attr(href)').get()
        name = " ".join(card.css('a[class*="line-clamp"]::text').get("").split())
        price_text = card.css("span.text-red-700::text").get("")
        match = re.search(r"\d[\d,]*(?:\.\d+)?", price_text)
        if not product_id or not url or not name or product_id in seen:
            continue
        try:
            price = Decimal(match.group(0).replace(",", "") if match else "")
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        parts = [part for part in urlparse(url).path.split("/") if part]
        category = parts[1].replace("-", " ").title() if len(parts) > 2 else None
        text = " ".join(card.css("::text").getall())
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": category,
            "price": format(price, "f"),
            "currency": "NPR",
            "country": "Nepal",
            "sector": "consumer_goods",
            "available": "Out of Stock" not in text,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class NepalKhushibazarSpider(scrapy.Spider):
    name = "nepal_khushibazar"
    allowed_domains = ["khushibazar.com.np", "www.khushibazar.com.np"]
    start_urls = ["https://www.khushibazar.com.np/products/stationery"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
