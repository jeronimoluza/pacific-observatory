"""Scrape AlcoArt Baku's paginated consumer-products catalogue."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import urlsplit

import scrapy


_PRICE_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*AZN")
_CATEGORY_URLS = [
    "https://alcoartbaku.com/en/category/drinks",
    "https://alcoartbaku.com/en/category/snus",
    "https://alcoartbaku.com/en/category/cigar-and-cigarillos",
    "https://alcoartbaku.com/en/category/tobacco",
    "https://alcoartbaku.com/en/category/hookah-products",
]


def clean(value):
    return " ".join(unescape(str(value or "")).split())


def parse_products(response):
    scraped_at = datetime.now(timezone.utc).isoformat()
    category = clean(response.meta.get("category") or "general merchandise")
    for card in response.css(".product-card"):
        url = card.css(".pc__title a::attr(href)").get()
        name = clean(" ".join(card.css(".pc__title a::text").getall()))
        prices = _PRICE_RE.findall(" ".join(card.css(".product-card__price ::text").getall()))
        if not url or not name or not prices:
            continue
        try:
            price = Decimal(prices[-1].replace(",", "."))
        except InvalidOperation:
            continue
        if price <= 0:
            continue
        slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
        if not slug:
            continue
        yield {
            "product_id": slug,
            "product_name": name[:500],
            "category": category[:500],
            "price": format(price, "f"),
            "currency": "AZN",
            "country": "Azerbaijan",
            "sector": "consumer_goods",
            "available": True,
            "url": response.urljoin(url),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class AzerbaijanAlcoartbakuSpider(scrapy.Spider):
    name = "azerbaijan_alcoartbaku"
    allowed_domains = ["alcoartbaku.com"]
    start_urls = _CATEGORY_URLS
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html",
            "Referer": "https://alcoartbaku.com/en/category",
        },
    }

    def parse(self, response):
        if not response.meta.get("category"):
            response.meta["category"] = response.url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        yield from parse_products(response)
        next_page = response.css("#load-more-btn::attr(data-page)").get()
        if next_page and next_page.isdigit() and int(next_page) <= 100:
            base_url = response.url.split("?", 1)[0]
            yield scrapy.Request(
                f"{base_url}?page={next_page}",
                callback=self.parse,
                meta={"category": response.meta.get("category")},
                headers={"X-Requested-With": "XMLHttpRequest", "Accept": "text/html"},
            )
