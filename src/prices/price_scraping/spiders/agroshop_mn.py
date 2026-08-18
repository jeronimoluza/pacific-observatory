"""
Spider for Agroshop (Mongolia) — https://agroshop.mn/.

WooCommerce store (the /product-category/ path is the WooCommerce tell).
Products are reachable via the public WooCommerce Store API at
/wp-json/wc/store/v1/products?per_page=100&page=N — no auth required.
Small catalog (~28 SKUs total across farming inputs, veterinary meds,
packaging, and food/organic-food categories); walk the whole store rather
than filtering to one category since the catalog is already tiny.

currency_minor_unit is 0 for this store (prices already whole MNT, e.g.
"180000" == 180,000₮), confirmed against the rendered price_html field in
the same payload — no rescaling bug here, but we still read
currency_minor_unit from the payload rather than assuming 0, per the
WooCommerce Store API minor-unit trap.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://agroshop.mn/wp-json/wc/store/v1/products"
PER_PAGE = 100
MAX_PAGES = 20  # safety cap; catalog is ~28 items


class AgroshopMnSpider(scrapy.Spider):
    name = "agroshop_mn"
    allowed_domains = ["agroshop.mn"]
    currency = "MNT"
    language = "mn"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 2.0,
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
            logger.warning(f"agroshop_mn: non-JSON response at {response.url}")
            return
        if not isinstance(products, list) or not products:
            return
        page = response.meta["page"]
        logger.info(f"agroshop_mn: page={page} count={len(products)}")
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
