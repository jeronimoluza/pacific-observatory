"""Scrape current product cards from BarryTech Guinea."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.product-card"):
        button = card.css("button[data-product-slug]")
        slug = (button.css("::attr(data-product-slug)").get() or "").strip()
        name = " ".join(card.css("h6.product-title").xpath("string(.)").get(default="").split())
        raw_price = (button.css("::attr(data-product-price)").get() or "").replace(",", ".")
        url = card.css('a[title="Voir les détails"]::attr(href)').get()
        if not slug or not name or not url or slug in seen:
            continue
        try:
            price = Decimal(raw_price)
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        seen.add(slug)
        yield {
            "product_id": slug,
            "product_name": name[:500],
            "category": "telecommunications equipment",
            "price": format(price, "f"),
            "currency": "GNF",
            "country": "Guinea",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "fr",
            "scraped_at_utc": scraped_at,
        }


class GuineaBarrytechSpider(scrapy.Spider):
    name = "guinea_barrytech"
    allowed_domains = ["barrytechguinee.com"]
    start_urls = ["https://barrytechguinee.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_cards(response)
