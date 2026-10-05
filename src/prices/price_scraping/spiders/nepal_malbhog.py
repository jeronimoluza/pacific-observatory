"""Scrape current featured products from Malbhog Nepal."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.product-card-modern"):
        onclick = card.css("button.product-btn-modern::attr(onclick)").get("")
        id_match = re.search(r"addToCart\((\d+)\)", onclick)
        product_id = id_match.group(1) if id_match else ""
        url = card.css("h3.product-title-modern a::attr(href)").get()
        name = " ".join(card.css("h3.product-title-modern a::text").get("").split())
        price_text = card.css("span.price-current-modern::text").get("")
        price_match = re.search(r"\d[\d,]*(?:\.\d+)?", price_text)
        if not product_id or not url or not name or product_id in seen:
            continue
        try:
            price = Decimal(
                price_match.group(0).replace(",", "") if price_match else ""
            )
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": "Featured Products",
            "price": format(price, "f"),
            "currency": "NPR",
            "country": "Nepal",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class NepalMalbhogSpider(scrapy.Spider):
    name = "nepal_malbhog"
    allowed_domains = ["malbhog.com", "www.malbhog.com"]
    start_urls = ["https://www.malbhog.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
