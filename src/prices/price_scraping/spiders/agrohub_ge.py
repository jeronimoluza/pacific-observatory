"""Agrohub -- https://agrohub.ge/ (Tbilisi, Georgia).

Agrohub is a Tbilisi full-line online supermarket ("shop" 1 = Marshal
Gelovani Ave. 22) running a Next.js SPA over a plain, unauthenticated REST
API at ``api.agrohub.ge``. The API is the same "lemondo" white-label family
as ``market.extra.ge``'s ``api.moitane.ge`` backend (identical
``/v1/Categories``, ``/v1/Banners/v2``, ``/v1/Products/...`` route shape) --
but unlike extra.ge, Agrohub's products-by-category endpoint is fully open,
so this is the first member of that platform family that can actually be
walked. The endpoint was found with a Playwright network trace on a category
page (the homepage alone only issues ``/v1/Products/Discount_Product``,
which is why an earlier pass on the sibling platform stalled).

Flow (all GET, all anonymous, no cookies, no TLS impersonation needed):

1. ``/v1/Categories?ShopId=1`` -> 30 top-level departments
   (``parentCategoryId == 0``) plus their subcategories. **Send
   ``Accept-Language: ka-GE``** -- the API otherwise returns English category
   names while product names stay Georgian.
2. ``/v1/Products/GetGroupedProducts?ShopId=1&ParentCategoryId=<top>&
   DiscountAsc=true&PageNumber=N&PageSize=50`` -> ``groupedProduct[]``, each
   group being one subcategory with its ``products[]``; ``productsCount`` is
   the department total and ``hasNextPage`` drives pagination.

Prices are plain GEL decimals (``price``: 2.95), NOT minor units --
``previousPrice`` carries the struck-through pre-promotion price and is
deliberately ignored, since ``price`` is what a shopper pays today.

``/v1/Shops`` and ``/v1/Products?ShopId=1`` both 401 without a session; they
are not needed. Note ``/product/<id>`` is NOT a route on the storefront
(Next.js resolves it to ``page: "/"``, i.e. the catch-all) -- product detail
is a client-side modal -- so ``url`` is synthesized as the owning department
page plus a ``#<product_id>`` fragment, per the globus_online_kg precedent
and the DuplicationPipeline url-dedup trap.
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://api.agrohub.ge/v1"
_SHOP_ID = "1"
_PAGE_SIZE = 50
_MAX_PAGES = 200


class AgrohubGeSpider(scrapy.Spider):
    name = "agrohub_ge"
    allowed_domains = ["api.agrohub.ge"]
    currency = "GEL"
    language = "ka"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "DOWNLOAD_DELAY": 0.4,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    HEADERS = {"Accept": "application/json", "Accept-Language": "ka-GE"}

    async def start(self):
        yield scrapy.Request(
            f"{_API}/Categories?ShopId={_SHOP_ID}",
            callback=self.parse_categories,
            headers=self.HEADERS,
            errback=self.errback,
        )

    def parse_categories(self, response):
        try:
            cats = json.loads(response.text).get("categories") or []
        except json.JSONDecodeError:
            logger.error("%s: non-JSON category payload", self.name)
            return
        tops = [c for c in cats if not c.get("parentCategoryId")]
        logger.info("%s: %d departments (of %d category rows)", self.name, len(tops), len(cats))
        for c in tops:
            yield self._page_request(c["id"], (c.get("name") or "").strip(), 1)

    def _page_request(self, cat_id, cat_name, page):
        return scrapy.Request(
            f"{_API}/Products/GetGroupedProducts?ShopId={_SHOP_ID}"
            f"&ParentCategoryId={cat_id}&DiscountAsc=true"
            f"&PageNumber={page}&PageSize={_PAGE_SIZE}",
            callback=self.parse_products,
            headers=self.HEADERS,
            meta={"cat_id": cat_id, "cat_name": cat_name, "page": page},
            errback=self.errback,
        )

    def parse_products(self, response):
        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]
        page = response.meta["page"]
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("%s: non-JSON products for cat %s p%d", self.name, cat_id, page)
            return

        groups = payload.get("groupedProduct") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        emitted = 0
        for group in groups:
            sub = (group.get("subCategoryName") or "").strip()
            path = " > ".join([p for p in (cat_name, sub) if p])
            for raw in group.get("products") or []:
                item = self._item(raw, cat_id, path, scraped_at)
                if item:
                    emitted += 1
                    yield item

        if payload.get("hasNextPage") and page < _MAX_PAGES and groups:
            yield self._page_request(cat_id, cat_name, page + 1)
        elif not groups:
            logger.debug("%s: cat %s exhausted at page %d", self.name, cat_id, page)

    def _item(self, raw: dict, cat_id, cat_path: str, scraped_at: str):
        name = (raw.get("name") or "").strip()
        price = raw.get("price")
        if not name or price in (None, ""):
            return None
        try:
            amount = float(price)
        except (TypeError, ValueError):
            return None
        if amount <= 0:
            return None
        pid = raw.get("barCode") or raw.get("id")
        return {
            "product_id": str(pid) if pid else None,
            "product_name": name,
            "category": cat_path or None,
            "price": f"{amount:.2f}",
            "currency": self.currency,
            "available": bool(raw.get("storageQuantity") or 0),
            "url": f"https://agrohub.ge/category/{cat_id}#{raw.get('id')}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }

    def errback(self, failure):
        logger.error(
            "%s: request failed %s — %r", self.name, failure.request.url, failure.value
        )
