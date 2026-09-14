"""Scrape current product cards from La Licorera Colombia."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


class ColombiaLalicoreraSpider(scrapy.Spider):
    name = "colombia_lalicorera"
    allowed_domains = ["lalicorera.com", "www.lalicorera.com"]
    start_urls = ["https://lalicorera.com/productos/cigarrillos"]

    def parse(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("article.product-card"):
            href = (card.css("a.price::attr(href)").get() or "").strip()
            name = " ".join(card.css("h3.name ::text").getall())
            name = " ".join(name.split())
            price_text = (card.css("a.price::text").get() or "").strip()
            match = re.search(r"\$\s*([0-9][0-9,.]*)", price_text)
            if not (href.startswith("/productos/") and name and match):
                continue
            try:
                price = Decimal(match.group(1).replace(",", ""))
            except InvalidOperation:
                continue
            if price <= 0:
                continue
            yield {
                "product_id": href.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name[:500],
                "price": str(price),
                "currency": "COP",
                "country": "Colombia",
                "sector": "consumer_goods",
                "available": True,
                "url": response.urljoin(href),
                "language": "es",
                "scraped_at_utc": scraped_at,
            }
