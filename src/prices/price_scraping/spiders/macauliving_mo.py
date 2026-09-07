"""Macau Living appliance, auto oil, and household catalog."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


_PRICE_RE = re.compile(r"[\d,.]+")


def _clean(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _price(text: str | None) -> str | None:
    if not text:
        return None
    match = _PRICE_RE.search(text.replace(",", ""))
    return match.group(0) if match else None


class MacaulivingMoSpider(scrapy.Spider):
    name = "macauliving_mo"
    allowed_domains = ["www.macauliving.com"]
    start_urls = ["https://www.macauliving.com/index.php?r=product%2Findex"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for box in response.css(".ny-product-box > ul > li"):
            href = box.css("a::attr(href)").get()
            brand = box.css(".ny-product-t1::text").get()
            title = box.css(".ny-product-t2::text").get()
            price = _price(box.css(".ny-product-price1::text").get())
            product_id = None
            if href:
                product_id = re.search(r"id=(\d+)", href)
            name = _clean([brand, title])
            if not name or not href or not price:
                continue
            yield {
                "product_id": product_id.group(1) if product_id else urljoin(response.url, href),
                "product_name": name[:500],
                "category": "Appliances, auto, and household goods",
                "price": price,
                "currency": "MOP",
                "available": True,
                "url": urljoin(response.url, href),
                "language": "zh-Hant",
                "scraped_at_utc": scraped_at,
            }

        next_href = response.css("ul.pagination li.next a::attr(href)").get()
        if next_href:
            yield response.follow(next_href, callback=self.parse)
