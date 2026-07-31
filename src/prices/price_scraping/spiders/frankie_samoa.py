"""
Spider for Frankie Online Shopping (Samoa) — https://frankiesamoa.com/.

Shopify storefront. Walks /products.json?limit=250&page=N until an empty page.
Each product has title, handle, vendor, product_type, variants[] with sku/price.
Currency from /shop.json (defaults to WST — Samoan Tala — on Frankie).

Note: SamoaMarket aggregator (farmer_joe spider) labels prices NZD because that
shop is hosted on a NZ-headquartered Shopify; Frankie's own storefront is
Samoa-hosted and prices in WST.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://frankiesamoa.com/products.json"
PER_PAGE = 250
MAX_PAGES = 200


class FrankieSamoaSpider(scrapy.Spider):
    name = "frankie_samoa"
    allowed_domains = ["frankiesamoa.com"]
    currency = "WST"
    language = "en"

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
        logger.info(f"frankie_samoa page={page} count={len(products)}")
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
                "category": product_type,
                "price": str(price),
                "currency": self.currency,
                "available": bool(v.get("available", True)),
                "url": f"https://frankiesamoa.com/products/{handle}?variant={v.get('id')}",
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
