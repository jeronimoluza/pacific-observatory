"""Spider for ShopIt Nepal (Nepal) — https://www.shopitnepal.com/.

Next.js frontend backed by a mobile JSON API, no auth. Re-verified live
2026-08-06: GET https://shopitnepal.com/api/mobile/products -> 200, paginated
20 items/page, `meta: {page, limit, total: 1376, totalPages: 69}`; `?page=2`
confirmed to return a different page (not a repeat). Sample: 'NIVEA Shea
Smooth 75ml' price=185 mrp=200. Quick-commerce convenience-store catalog
(cloud kitchen, liquor, smokes, sweets, daily groceries) — currency NPR
(matches countries.yaml). Products carry no category reference in this
payload, so category is left null.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_URL = "https://shopitnepal.com/api/mobile/products"
_MAX_PAGES = 100  # safety cap; live total was 69 pages


class ShopitnepalNpSpider(scrapy.Spider):
    name = "shopitnepal_np"
    allowed_domains = ["shopitnepal.com"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
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
            f"{_URL}?page=1",
            callback=self.parse_page,
            meta={"page": 1},
        )

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning(f"shopitnepal_np: non-JSON response at {response.url}")
            return
        products = payload.get("data") or []
        meta = payload.get("meta") or {}
        page = response.meta["page"]
        total_pages = meta.get("totalPages") or payload.get("totalPage") or page
        logger.info(
            f"shopitnepal_np page={page} count={len(products)} totalPages={total_pages}"
        )
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in products:
            item = self._item(p, scraped_at)
            if item:
                yield item
        if products and page < total_pages and page < _MAX_PAGES:
            nxt = page + 1
            yield scrapy.Request(
                f"{_URL}?page={nxt}",
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, p: dict, scraped_at: str):
        price = p.get("price")
        if price is None:
            return None
        status = str(p.get("stockStatus") or "").lower()
        product_id = str(p.get("id") or "")
        return {
            "product_id": product_id,
            "product_name": str(p.get("name") or "").strip()[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": status not in {"out_of_stock", "unavailable"},
            "url": f"https://www.shopitnepal.com/#{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
