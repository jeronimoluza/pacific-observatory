"""Scrape Tienda Ecuador's public WooCommerce Store API."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape

import scrapy


API_URL = "https://tiendaecuador.ec/wp-json/wc/store/v1/products?per_page=100"
API_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://tiendaecuador.ec/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
}


def parse_products(products: list[dict], scraped_at: str):
    for product in products:
        prices = product.get("prices") or {}
        product_id = product.get("id")
        name = " ".join(unescape(str(product.get("name") or "")).split())
        url = str(product.get("permalink") or "").strip()
        raw_price = prices.get("price")
        if not (product_id and name and url and raw_price):
            continue
        if prices.get("currency_code") != "USD":
            continue
        try:
            minor_unit = int(prices.get("currency_minor_unit", 2))
            price = Decimal(str(raw_price)) / (Decimal(10) ** minor_unit)
        except (InvalidOperation, TypeError, ValueError):
            continue
        if price <= 0:
            continue
        yield {
            "product_id": str(product_id),
            "product_name": name[:500],
            "price": f"{price:.{minor_unit}f}",
            "currency": "USD",
            "country": "Ecuador",
            "sector": "consumer_goods",
            "available": bool(product.get("is_in_stock", False)),
            "url": url,
            "language": "es",
            "scraped_at_utc": scraped_at,
        }


class EcuadorTiendaecuadorEcSpider(scrapy.Spider):
    name = "ecuador_tiendaecuador_ec"
    allowed_domains = ["tiendaecuador.ec", "www.tiendaecuador.ec"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 0.5}

    async def start(self):
        yield scrapy.Request(API_URL, headers=API_HEADERS, callback=self.parse)

    def parse(self, response):
        yield from parse_products(response.json(), datetime.now(timezone.utc).isoformat())
