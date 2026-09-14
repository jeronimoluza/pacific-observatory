"""Scrape Kokomo Markets Belize's public WooCommerce Store API."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import scrapy


class KokomoMarketsBZSpider(scrapy.Spider):
    name = "kokomomarkets_bz"
    allowed_domains = ["kokomomarkets.com"]
    start_urls = [
        "https://kokomomarkets.com/wp-json/wc/store/v1/products?per_page=100&page=1"
    ]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/json",
            "Referer": "https://kokomomarkets.com/shop/",
        },
    }

    def parse(self, response):
        try:
            products = response.json()
        except ValueError:
            return
        if not isinstance(products, list):
            return
        scraped_at = datetime.now(timezone.utc).isoformat()
        for product in products:
            prices = product.get("prices") or {}
            product_id = str(product.get("id") or "").strip()
            name = " ".join(str(product.get("name") or "").split())
            url = product.get("permalink")
            if prices.get("currency_code") != "USD":
                continue
            try:
                amount = Decimal(str(prices.get("price"))) / (
                    Decimal(10) ** int(prices.get("currency_minor_unit") or 0)
                )
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not product_id or not name or not url or amount <= 0:
                continue
            categories = product.get("categories") or []
            category = categories[0].get("name") if categories and isinstance(categories[0], dict) else "general merchandise"
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": str(category)[:500],
                "price": format(amount, "f"),
                "currency": "USD",
                "country": "Belize",
                "sector": "consumer_goods",
                "available": bool(product.get("is_in_stock", True)),
                "url": url,
                "language": "en",
                "scraped_at_utc": scraped_at,
            }
        page = int(response.meta.get("page", 1))
        if len(products) == 100 and page < 100:
            next_page = page + 1
            yield scrapy.Request(
                f"https://kokomomarkets.com/wp-json/wc/store/v1/products?per_page=100&page={next_page}",
                callback=self.parse,
                meta={"page": next_page},
            )
