"""Scrape active products embedded by Diana Trading Maldives."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


def parse_products(response):
    raw = response.css("script#__NEXT_DATA__::text").get()
    if not raw:
        return
    try:
        data = json.loads(raw)["props"]["pageProps"]["data"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return
    products = list(data.get("featured_products") or [])
    products.extend(
        row.get("product") for row in (data.get("best_selling") or [])
        if isinstance(row, dict)
    )
    scraped_at = datetime.now(timezone.utc).isoformat()
    seen = set()
    for product in products:
        if not isinstance(product, dict) or product.get("status") != "active":
            continue
        product_id = str(product.get("id") or "").strip()
        slug = str(product.get("slug") or "").strip()
        name = " ".join(str(product.get("name") or "").split())
        if not product_id or not slug or not name or product_id in seen:
            continue
        try:
            price = Decimal(str(product.get("price")))
        except (InvalidOperation, TypeError):
            continue
        if price <= 0:
            continue
        seen.add(product_id)
        stock_text = str(product.get("sku") or "").lower()
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": format(price, "f"),
            "currency": "MVR",
            "country": "Maldives",
            "sector": "consumer_goods",
            "available": "out of stock" not in stock_text,
            "url": response.urljoin(f"/product/{slug}"),
            "language": "en",
            "scraped_at_utc": scraped_at,
        }


class MaldivesDianatradingSpider(scrapy.Spider):
    name = "maldives_dianatrading"
    allowed_domains = ["dianatradingmv.com", "www.dianatradingmv.com"]
    start_urls = ["https://www.dianatradingmv.com/"]
    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 1, "DOWNLOAD_DELAY": 1.0}

    def parse(self, response):
        yield from parse_products(response)
