"""Goldunited Brunei hardware and building materials catalog."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


_PRICE_RE = re.compile(r"[\d,.]+")


def _price(text: str | None) -> str | None:
    if not text:
        return None
    match = _PRICE_RE.search(text.replace(",", ""))
    return match.group(0) if match else None


class GoldunitedBnSpider(scrapy.Spider):
    name = "goldunited_bn"
    allowed_domains = ["goldunited.com"]
    start_urls = ["https://goldunited.com/"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 2,
    }

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("article.card"):
            name = card.css(".card-title a::text").get()
            href = card.css(".card-title a::attr(href)").get()
            price = _price(card.css(".price--withoutTax::text").get())
            product_id = (
                card.css(".quickview::attr(data-product-id)").get()
                or card.css('a[href*="product_id="]::attr(href)').re_first(r"product_id=(\d+)")
            )
            if not name or not href or not price:
                continue
            yield {
                "product_id": product_id or urljoin(response.url, href),
                "product_name": name.strip()[:500],
                "category": "Hardware and building materials",
                "price": price,
                "currency": "BND",
                "available": True,
                "url": urljoin(response.url, href),
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
