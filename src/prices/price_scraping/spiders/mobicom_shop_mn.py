"""
Spider for Mobicom Shop (Mongolia) — https://www.mobicom.mn/.

The public storefront (www.mobicom.mn) is a statically-exported Next.js
shell with empty pageProps — no product data in the HTML at all. Playwright
network trace of the "new number / choose package" flow found the real
backend: osa.mobicom.mn, a Strapi CMS on a sibling host, called with no
auth and no special headers. `GET /api/products` returns the ENTIRE device
catalogue (handsets/tablets/accessories, 98 items) in a single unpaginated
response — page/pagination[page] query params are accepted but silently
ignored (verified: page=1 and page=2 return byte-identical data). Prices
are plain integer MNT (no minor-unit division), e.g. "iPhone 17" ->
price=4249000, listPrice=4509000 (list/regular vs current price).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

API_URL = "https://osa.mobicom.mn/api/products"


class MobicomShopMnSpider(scrapy.Spider):
    name = "mobicom_shop_mn"
    allowed_domains = ["osa.mobicom.mn"]
    currency = "MNT"
    language = "mn"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_TIMEOUT": 30,
    }

    async def start(self):
        yield scrapy.Request(API_URL, callback=self.parse_products)

    def parse_products(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"mobicom_shop_mn: non-JSON response at {response.url}")
            return
        products = payload.get("data") or []
        logger.info(f"mobicom_shop_mn: count={len(products)}")
        for p in products:
            item = self._item(p)
            if item:
                yield item

    def _item(self, p: dict):
        name = (p.get("name_en") or p.get("name_mn") or "").strip()
        price = p.get("price")
        pid = p.get("id")
        if not name or price is None or pid is None:
            return None
        category = {1: "Handset", 2: "Accessories", 3: "Tablet"}.get(p.get("categoryId"))
        return {
            "product_id": str(pid),
            "product_name": name[:500],
            "price": str(price),
            "currency": self.currency,
            "category": category,
            "url": f"https://www.mobicom.mn/shop?catId={p.get('categoryId')}#product-{pid}",
            "language": self.language,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
