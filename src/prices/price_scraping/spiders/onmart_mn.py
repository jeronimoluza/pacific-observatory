"""
Spider for Onmart (Mongolia) — https://onmart.mn/.

Storefront is a Next.js app; the product list itself is served by an open
JSON API on the sibling host api.onmart.mn (no auth, no Origin/Referer
required — confirmed via curl). /api/products returns {products, totalDoc,
limits, pages} paginated with ?page=N, 20 items/page, ~2,346 products total.
Product titles and descriptions are Cyrillic Mongolian despite living under
a "title.en" / "description.en" key (site has no other locale configured).
Prices are plain decimal strings in whole MNT (no minor-unit division
needed) — verified against the rendered PDP ("OMO 1.5кг" showed 8,900₮ on
page, "prices.price": "8900.00" from the API for the matching id).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_BASE = "https://api.onmart.mn/api/products"
PAGE_SIZE = 20
MAX_PAGES = 200  # safety cap (~2,346 products / 20 per page ~= 118 pages)


class OnmartMnSpider(scrapy.Spider):
    name = "onmart_mn"
    allowed_domains = ["api.onmart.mn"]
    currency = "MNT"
    language = "mn"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    async def start(self):
        yield scrapy.Request(
            f"{API_BASE}?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"onmart_mn: non-JSON response at {response.url}")
            return
        products = payload.get("products") or []
        page = response.meta["page"]
        logger.info(f"onmart_mn: page={page} count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item
        if len(products) >= PAGE_SIZE and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{API_BASE}?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict):
        title = ((p.get("title") or {}).get("en") or "").strip()
        prices = p.get("prices") or {}
        price = prices.get("price") or prices.get("originalPrice")
        if not title or price is None:
            return None
        category = (p.get("category") or {}).get("name")
        pid = p.get("id") or p.get("productId")
        return {
            "product_id": str(pid) if pid else None,
            "product_name": title[:500],
            "price": str(price),
            "currency": self.currency,
            "category": category,
            "available": str(p.get("stock") or "0") not in ("0", "0.00"),
            "url": f"https://onmart.mn/product/{p.get('id')}" if p.get("id") else "",
            "language": self.language,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
