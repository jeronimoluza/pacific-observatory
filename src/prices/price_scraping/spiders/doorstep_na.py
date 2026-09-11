"""
Doorstep Deliveries -- https://shop.com.na/ (Windhoek, Namibia: alcohol,
tobacco, soft drinks and snack/braai delivery -- "general goods delivery").

Custom Next.js storefront, not one of the known off-the-shelf platforms.
Network-traced the app's own JS chunks (Playwright not needed --
app/layout-*.js references the routes directly): a plain, unauthenticated
JSON API at /api/products returns the full catalogue in a single response.

No real pagination: `page=`/`offset=` params are accepted but ignored
(identical first row regardless of page number), and raising `limit=` past
the true catalogue size does not return more rows -- confirmed the 96 rows
returned is the whole catalogue by cross-checking that /api/categories'
22 categories are all represented in the 96 products. This is a genuinely
small, single-page-holds-everything catalogue, not a paginator stuck on
page 1.

Prices are plain decimal NAD (e.g. "65" -> N$65.00, no minor-unit
scaling) -- there is no currency field in the payload, but NAD (not ZAR)
appears on the storefront itself and this is a Windhoek-only delivery
app. Each product has exactly one variant (verified: 0 of 96 products
carry >1 variant); `dayPrice`/`nightPrice` both exist per variant --
dayPrice (variants[].price) is used as the reference retail price.
"""

import html
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_URL = "https://shop.com.na/api/products"


class DoorstepNaSpider(scrapy.Spider):
    name = "doorstep_na"
    allowed_domains = ["shop.com.na"]
    currency = "NAD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_API_URL, callback=self.parse_products)

    def parse_products(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("doorstep_na: non-JSON response at %s", response.url)
            return
        products = payload.get("products") or []
        logger.info("doorstep_na: %s products", len(products))
        for p in products:
            item = self._item(p)
            if item:
                yield item

    def _item(self, p: dict):
        variants = p.get("variants") or []
        if not variants:
            return None
        variant = variants[0]
        price = variant.get("price")
        if price is None:
            return None
        try:
            if float(price) == 0:
                return None
        except (TypeError, ValueError):
            return None

        name = html.unescape(str(p.get("name") or "")).strip()
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            return None

        slug = p.get("slug")
        return {
            "product_id": str(variant.get("barcode") or p.get("articleCode") or ""),
            "product_name": name[:500],
            "category": p.get("category"),
            "price": str(price),
            "currency": self.currency,
            "available": (p.get("inventory") or 0) > 0,
            "url": f"https://shop.com.na/products/{slug}" if slug else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
