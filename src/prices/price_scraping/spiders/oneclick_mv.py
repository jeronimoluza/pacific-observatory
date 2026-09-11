"""
Spider for Oneclick Maldives — oneclick.com.mv, "Maldives' Trusted Food
& Beverage Distributor" (self-described), operating a consumer-facing
WooCommerce storefront.

WooCommerce Store API, no auth: /wp-json/wc/store/v1/products?per_page=N
Confirmed 234 products total (X-WP-Total header). currency_minor_unit=2
confirmed in the payload (e.g. "500" -> MVR 5.00 for "Normal Sugar 1Kg"),
divided per the standard WooCommerce Store API minor-unit trap rather
than assumed.

Page family: API only — the spider never fetches an HTML page.

Verified live 2026-09-11: page 1 (--max-items 5) returned 5 rows.
Sample: "Milk Short Cake 12x45g" MVR 47.00, "Normal Sugar 1Kg" MVR 5.00,
"Normal Flour 1Kg" MVR 5.00.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://oneclick.com.mv/wp-json/wc/store/v1/products"
PER_PAGE = 50
MAX_PAGES = 20  # safety cap; catalog is ~234 items


class OneclickMvSpider(scrapy.Spider):
    name = "oneclick_mv"
    allowed_domains = ["oneclick.com.mv"]
    currency = "MVR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "ROBOTSTXT_OBEY": False,
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE}?per_page={PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            products = response.json()
        except ValueError:
            logger.warning(f"oneclick_mv: non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"oneclick_mv: page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?per_page={PER_PAGE}&page={nxt}",
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
