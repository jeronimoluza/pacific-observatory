"""
Go Plus (Madagascar) — https://goplus.arato.mg/.

General marketplace (electronics, MacBooks, school supplies, crafts, baby
items, sports, food/wellness). Its unauthenticated JSON API at
api-go-plus.arato.mg serves the ENTIRE catalogue in a single response —
GET /api/products returns all products at once; a page/limit query param
does not change the result (verified live 2026-09-10: ?page=2 and
?page=2&limit=50 both return the same 178 products, byte-identical to
page 1). There is no pagination to walk because there is nothing to
paginate: this is a single complete catalogue dump, not a windowed feed.

/api/categories mirrors the same 178 products nested under 13 categories
-- redundant with /api/products, not used here.

Verified live 2026-09-10: 178 products, all isAvailable=true, zero
zero-price rows, prices MGA 400 - 2,800,000 (e.g. "MacBook Pro 2016 A1707"
at MGA 2,800,000; "Surligneur schneider Job" at MGA 4,500). Currency is
MGA (Malagasy Ariary) per the brief; the API itself does not label a
currency field, prices are plain numbers consistent with MGA magnitudes.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class GoplusMgSpider(scrapy.Spider):
    name = "goplus_mg"
    allowed_domains = ["api-go-plus.arato.mg"]
    currency = "MGA"
    language = "fr"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
    }

    async def start(self):
        yield scrapy.Request(
            "https://api-go-plus.arato.mg/api/products",
            headers={
                "Accept": "application/json",
                "Origin": "https://goplus.arato.mg",
                "Referer": "https://goplus.arato.mg/",
            },
            callback=self.parse_products,
        )

    def parse_products(self, response):
        try:
            products = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"{self.name}: JSON decode failed for {response.url}")
            return
        if not isinstance(products, list):
            logger.error(f"{self.name}: unexpected payload shape at {response.url}")
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for p in products:
            item = self._item(p, scraped_at)
            if item:
                n += 1
                yield item
        logger.info(f"{self.name}: emitted {n} of {len(products)} products")

    def _item(self, p: dict, scraped_at: str):
        if not p.get("isAvailable", True):
            return None
        try:
            price = float(p.get("price"))
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        name = (p.get("name") or "").strip()
        if not name:
            return None
        category = (p.get("category") or {}).get("name")
        return {
            "product_id": p.get("id"),
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": True,
            "url": f"https://goplus.arato.mg/products/{p.get('id')}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
