"""Spider for Groceries Nepal (Nepal) — https://groceriesnepal.com/.

React/Vite SPA backed by a plain JSON API, no auth. Re-verified live
2026-08-06: GET https://groceriesnepal.com/api/products -> 200, ~26KB JSON,
a flat list of 97 products (no pagination — the whole catalog in one
response). Sample: 'Tomato (Goalbheda)' category=Vegetables price=100 unit=kg.
Small but genuinely carries fresh Vegetables/Leafy Vegetables/Fruits
categories alongside Dairy/Grocery. Currency NPR (matches countries.yaml).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://groceriesnepal.com/api/products"


class GroceriesnepalNpSpider(scrapy.Spider):
    name = "groceriesnepal_np"
    allowed_domains = ["groceriesnepal.com"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(_URL, callback=self.parse)

    def parse(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning("groceriesnepal_np: non-JSON response")
            return
        if not isinstance(products, list):
            return
        logger.info(f"groceriesnepal_np: count={len(products)}")
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            price = p.get("price")
            if price is None:
                continue
            product_id = str(p.get("id") or "")
            yield {
                "product_id": product_id,
                "product_name": str(p.get("name") or "").strip()[:500],
                "category": p.get("category") or None,
                "price": str(price),
                "currency": self.currency,
                "available": bool(p.get("inStock", True)),
                "url": f"https://groceriesnepal.com/#{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
