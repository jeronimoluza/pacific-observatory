"""
Spider for Araz Market (Azerbaijan) — https://arazmarket.az/

Numeric-id-walk over the storefront's own Laravel JSON backend. The SPA at
arazmarket.az renders its catalog client-side; the backend lives on a
separate host, https://b7x9kq.arazmarket.az/api, and is unauthenticated.

Only two routes are reachable there (probed live 2026-09-11):
  /api/categories        -> the full category tree, but NO products in it
  /api/products/<id>     -> one product, with sales_price / discount_price
There is no category-products or search route (every plausible name returns
a Laravel "route could not be found" 404), so the catalog cannot be
enumerated by category. The numeric id walk is the only enumeration path.

Id space: sparse, ~44% live on a 62-point sample across 1..6000, with hits
as high as 5918. Live ids run to at least 11514; 14000+ is entirely dead, so 1..13000 is the working range.

Each product response also carries a `recommended` array of up to ~6 sibling
products with the SAME full payload shape (title, barcode, both prices,
category) — those are harvested too, deduped by id, which materially raises
yield per request.

Price: `discount_price` is the price actually charged when `is_discount` is
true; `sales_price` is the shelf/list price. We emit the charged price.
Currency AZN (matches countries.yaml); the API states no currency code.

Page family parsed: API. Collected urls are /az/products/<slug> storefront
permalinks the spider never fetches.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)

API = "https://b7x9kq.arazmarket.az/api/products/"
MAX_ID = 13000


class ArazmarketAzSpider(scrapy.Spider):
    name = "arazmarket_az"
    allowed_domains = ["b7x9kq.arazmarket.az"]
    currency = "AZN"
    language = "az"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.3,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "HTTPERROR_ALLOWED_CODES": [404],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen: set[int] = set()

    async def start(self):
        headers = {
            "Accept": "application/json",
            "Origin": "https://arazmarket.az",
            "Referer": "https://arazmarket.az/",
        }
        for pid in range(1, MAX_ID + 1):
            yield scrapy.Request(
                f"{API}{pid}", headers=headers, callback=self.parse_product
            )

    def parse_product(self, response):
        if response.status != 200:
            return
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            return
        product = (payload.get("data") or {}).get("product")
        if not isinstance(product, dict):
            return
        for p in [product, *(product.get("recommended") or [])]:
            item = self._item(p)
            if item:
                yield item

    def _item(self, p):
        if not isinstance(p, dict):
            return None
        pid = p.get("id")
        if pid in self.seen:
            return None
        title = (p.get("title") or "").strip()
        price = p.get("discount_price") if p.get("is_discount") else p.get("sales_price")
        if price is None:
            price = p.get("sales_price")
        try:
            if price is None or float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None
        if not title:
            return None
        self.seen.add(pid)
        slug = p.get("slug")
        return {
            "product_id": str(p.get("barcode") or pid),
            "product_name": title[:500],
            "category": p.get("category_title"),
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://arazmarket.az/az/products/{slug}" if slug else None,
            "language": self.language,
            "scraped_at_utc": response_time(),
        }


def response_time():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
