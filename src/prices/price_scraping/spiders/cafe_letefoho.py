"""
Spider for Café Letefoho (Timor-Leste) — https://cafeletefoho.com.

Single specialty coffee roaster on WooCommerce. The public WooCommerce Store
API at /wp-json/wc/store/v1/products?per_page=100&page=N returns full product
objects with name, sku, prices.{price,currency_code,currency_minor_unit},
categories, permalink. Prices are quoted in USD (Timor-Leste uses USD);
WooCommerce returns integer minor units (minor_unit=2 → 800 = $8.00).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://cafeletefoho.com/wp-json/wc/store/v1/products"
_PER_PAGE = 100
_MAX_PAGES = 20


class CafeLetefohoSpider(scrapy.Spider):
    name = "cafe_letefoho"
    allowed_domains = ["cafeletefoho.com"]
    currency = "USD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
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
            f"{_BASE}?per_page={_PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning("cafe_letefoho: non-JSON response at %s", response.url)
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= _PER_PAGE and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_BASE}?per_page={_PER_PAGE}&page={nxt}",
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
