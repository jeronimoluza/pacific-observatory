"""Scrape current catalogue cards from China Center Afghanistan."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


PRICE_RE = re.compile(r"AFN\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)


def parse_cards(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for card in response.css("article.group"):
        link = card.css("a.line-clamp-2")
        url = link.css("::attr(href)").get()
        name = " ".join(unescape(link.xpath("string(.)").get() or "").split())
        if not url or not url.startswith("/en/catalogue/") or not name:
            continue
        product_id = url.rstrip("/").rsplit("/", 1)[-1]
        if product_id in seen:
            continue

        retail_prices = card.xpath(
            "./div[contains(@class, 'flex-1')]/div[1]"
            "//span[@data-numeric='true']/text()"
        ).getall()
        match = PRICE_RE.search(retail_prices[-1] if retail_prices else "")
        if not match:
            continue
        try:
            price = Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        if price <= 0:
            continue

        stock_text = " ".join(card.xpath("string(.)").get().split()).lower()
        seen.add(product_id)
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": "general merchandise",
            "price": format(price, "f"),
            "currency": "AFN",
            "country": "Afghanistan",
            "sector": "consumer_goods",
            "available": "out of stock" not in stock_text,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class AfghanistanChinacenterSpider(scrapy.Spider):
    name = "afghanistan_chinacenter"
    allowed_domains = ["afghanchinashoppingcenter.com"]
    start_urls = ["https://afghanchinashoppingcenter.com/en/catalogue"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    def parse(self, response):
        yield from parse_cards(response)
