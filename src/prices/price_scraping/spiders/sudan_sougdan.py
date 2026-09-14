"""Scrape current product cards from Sougdan Sudan."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("div.project.item"):
        data = card.css("a.add_to_cart[data-product-id]")
        product_id = (data.css("::attr(data-product-id)").get() or "").strip()
        name = " ".join((data.css("::attr(data-product-title)").get() or "").split())
        raw_price = data.css("::attr(data-product-price)").get()
        url = card.css("h4.post-title a::attr(href)").get()
        stock = (data.css("::attr(data-product-stock)").get() or "").strip()
        if not product_id or not name or not raw_price or not url or product_id in seen:
            continue
        try:
            price = Decimal(raw_price.replace(",", ""))
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
            "currency": "SDG",
            "country": "Sudan",
            "sector": "consumer_goods",
            "available": stock != "0",
            "url": response.urljoin(url),
            "language": "ar",
            "scraped_at_utc": scraped_at,
        }


class SudanSougdanSpider(scrapy.Spider):
    name = "sudan_sougdan"
    allowed_domains = ["sougdan.com"]
    start_urls = ["https://sougdan.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_cards(response)
