"""
Spider for Common Health Myanmar - https://www.commonhealth.com.mm/

Shopify storefront for a chronic-disease pharmacy (insulin, pen needles,
glucose supplies). Catalogue exposed via the standard Shopify /products.json
endpoint, paginated with limit/page. Single vendor ("Common Health Myanmar").
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://www.commonhealth.com.mm/products.json"
PER_PAGE = 250
MAX_PAGES = 40


class CommonHealthSpider(scrapy.Spider):
    name = "common_health"
    allowed_domains = ["commonhealth.com.mm"]
    currency = "MMK"
    language = "my"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{BASE}?limit={PER_PAGE}&page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        products = data.get("products") if isinstance(data, dict) else None
        if not products:
            return
        page = response.meta["page"]
        logger.info(f"common_health page={page} count={len(products)}")
        for p in products:
            for item in self._items(p):
                yield item
        if len(products) >= PER_PAGE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?limit={PER_PAGE}&page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _items(self, p: dict):
        title = (p.get("title") or "").strip()
        handle = p.get("handle") or ""
        product_type = p.get("product_type") or None
        vendor = p.get("vendor") or None
        variants = p.get("variants") or []
        if not (title and variants):
            return
        for v in variants:
            if not isinstance(v, dict):
                continue
            price = v.get("price")
            if not price:
                continue
            sku = v.get("sku") or v.get("id") or p.get("id")
            v_title = (v.get("title") or "").strip()
            name = title if v_title in ("Default Title", "") else f"{title} ({v_title})"
            yield {
                "product_id": str(sku),
                "product_name": name[:500],
                "brand": vendor,
                "category": product_type or None,
                "price": str(price),
                "currency": self.currency,
                "available": bool(v.get("available", True)),
                "url": f"https://www.commonhealth.com.mm/products/{handle}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
