"""Nubri Mart's public Kathmandu grocery storefront."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


class NubrimartNpSpider(scrapy.Spider):
    name = "nubrimart_np"
    allowed_domains = ["www.nubrimart.com"]
    start_urls = ["https://www.nubrimart.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    def parse(self, response):
        for card in response.css("article.product-shop-card"):
            link = card.css("a.product-shop-main::attr(href)").get()
            name = card.css(".product-shop-name::text").get()
            raw_price = card.css(".product-shop-price strong::text").get()
            if not (link and name and raw_price):
                continue
            try:
                price = Decimal(raw_price.replace("Rs", "").replace(",", "").strip())
            except InvalidOperation:
                continue
            if price <= 0:
                continue
            yield {
                "product_id": link.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name.strip()[:500],
                "price": format(price, "f"),
                "currency": "NPR",
                "country": "Nepal",
                "sector": "consumer_goods",
                "url": response.urljoin(link),
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
