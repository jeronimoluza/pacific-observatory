"""Scrape Marketland Paraguay's public WooCommerce Store API."""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape

import scrapy


API_URL = "https://marketland.com.py/wp-json/wc/store/v1/products?per_page=100"
API_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://marketland.com.py/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36"
    ),
}


def _text(value: object) -> str:
    return " ".join(unescape(str(value or "")).split())


def parse_products(products: list[dict], scraped_at: str):
    """Yield schema-compatible rows from one Store API response page."""
    for product in products:
        prices = product.get("prices") or {}
        product_id = product.get("id")
        name = _text(product.get("name"))
        url = _text(product.get("permalink"))
        raw_price = prices.get("price")
        if not (product_id and name and url and raw_price):
            continue
        if prices.get("currency_code") != "PYG":
            continue
        try:
            if int(prices.get("currency_minor_unit", 0)) != 0 or int(raw_price) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        yield {
            "product_id": str(product_id),
            "product_name": name[:500],
            "price": str(int(raw_price)),
            "currency": "PYG",
            "country": "Paraguay",
            "sector": "consumer_goods",
            "available": bool(product.get("is_in_stock", False)),
            "url": url,
            "language": "es",
            "scraped_at_utc": scraped_at,
        }


class ParaguayMarketlandPySpider(scrapy.Spider):
    name = "paraguay_marketland_py"
    allowed_domains = ["marketland.com.py"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request(API_URL, headers=API_HEADERS, callback=self.parse)

    def parse(self, response):
        yield from parse_products(response.json(), datetime.now(timezone.utc).isoformat())
