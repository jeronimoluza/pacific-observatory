"""
Spider for Tonga Market (Tonga) — https://tongamarket.com/.

Multi-vendor WooCommerce marketplace on WordPress. The Groceries category
(https://tongamarket.com/product-category/groceries/, category id=97, ~466
items) is reachable via the public WooCommerce Store API at
/wp-json/wc/store/v1/products?category=97&per_page=100&page=N, which returns
full product objects with name, sku, prices.{price,currency_code,
currency_minor_unit}, categories, permalink, is_in_stock. We paginate that
endpoint (filtered to the groceries category) until a short/empty page is
returned.

Note: WooCommerce returns integer prices in the smallest currency unit; the
Store API exposes currency_minor_unit so we can rescale (e.g. minor_unit=2
means 2430 -> $24.30). Tonga Market prices in NZD per their store currency
(confirmed via probe), not Tonga's own TOP.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://tongamarket.com/wp-json/wc/store/v1/products"
GROCERIES_CATEGORY_ID = 97
PER_PAGE = 100
MAX_PAGES = 200  # safety cap


class TongamarketSpider(scrapy.Spider):
    name = "tongamarket"
    allowed_domains = ["tongamarket.com"]
    currency = "NZD"
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
        yield scrapy.Request(
            f"{BASE}?category={GROCERIES_CATEGORY_ID}&per_page={PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"tongamarket page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?category={GROCERIES_CATEGORY_ID}&per_page={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict):
        prices = p.get("prices") or {}
        raw = prices.get("price")
        if raw is None:
            return None
        try:
            minor = int(prices.get("currency_minor_unit", 0) or 0)
            value = int(raw) / (10**minor) if minor else int(raw)
        except (TypeError, ValueError):
            value = raw
        cats = p.get("categories") or []
        cat = (
            " > ".join(
                c.get("name") for c in cats if isinstance(c, dict) and c.get("name")
            )
            or None
        )
        return {
            "product_id": str(p.get("sku") or p.get("id")),
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": cat,
            "price": str(value),
            "currency": prices.get("currency_code") or self.currency,
            "available": bool(p.get("is_in_stock", True)),
            "url": p.get("permalink") or "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
