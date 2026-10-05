"""Scrape current device offers from Bhutan Telecom."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("article.eael-grid-post"):
        product_id = card.attrib.get("data-id", "").strip()
        title = card.css("h2.eael-entry-title a")
        url = title.attrib.get("href") if title else None
        name = " ".join(title.css("::text").get("").split()) if title else ""
        price_text = card.css("div.eael-grid-post-excerpt p::text").get("")
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
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": "Devices",
            "price": format(price, "f"),
            "currency": "BTN",
            "country": "Bhutan",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class BhutanTelecomDevicesSpider(scrapy.Spider):
    name = "bhutan_telecom_devices"
    allowed_domains = ["bt.bt", "www.bt.bt"]
    start_urls = ["https://www.bt.bt/product/iphone-17-pro/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
