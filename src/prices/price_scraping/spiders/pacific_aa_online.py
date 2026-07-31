"""
Spider for Pacific-AA Online Shop (Myanmar) - https://onlineshop.aa.com.mm/

AA Medical Products, the largest pharmaceutical distributor in Myanmar.
Laravel storefront. The catalogue page /all-products renders each product as
a Vue `<product :product='{...JSON...}'>` component whose escaped JSON payload
carries product_id (SKU), product_name, uom, slug and an `sprices` history
array. The current retail price is the most recently updated `sprices` entry.
Paginated via ?page=N (15 products/page).
"""

import html as ihtml
import json
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE = "https://onlineshop.aa.com.mm/all-products"
MAX_PAGES = 30
CARD_RE = re.compile(r":product='(\{.*?\})'", re.S)


class PacificAaOnlineSpider(scrapy.Spider):
    name = "pacific_aa_online"
    allowed_domains = ["onlineshop.aa.com.mm"]
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

    def start_requests(self):
        yield scrapy.Request(
            f"{BASE}?page=1", callback=self.parse_page, meta={"page": 1}
        )

    def parse_page(self, response):
        page = response.meta["page"]
        count = 0
        for blob in CARD_RE.findall(response.text):
            try:
                d = json.loads(ihtml.unescape(blob))
            except (ValueError, TypeError):
                continue
            item = self._item(d)
            if item is None:
                continue
            count += 1
            yield item
        logger.info(f"pacific_aa_online page={page} count={count}")
        if count > 0 and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{BASE}?page={nxt}", callback=self.parse_page, meta={"page": nxt}
            )

    def _item(self, d: dict):
        name = (d.get("product_name") or "").strip()
        if not name:
            return None
        sprices = d.get("sprices") or []
        current = None
        if sprices:
            latest = sorted(sprices, key=lambda x: x.get("updated_at") or "")[-1]
            current = latest.get("price")
        if current is None:
            return None
        slug = d.get("slug") or ""
        uom = d.get("uom") or None
        return {
            "product_id": d.get("product_id") or d.get("id"),
            "product_name": name[:500],
            "brand": None,
            "category": uom,
            "price": str(current),
            "currency": self.currency,
            "available": bool(d.get("saleable", 1)),
            "url": f"https://onlineshop.aa.com.mm/all-products?slug={slug}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
