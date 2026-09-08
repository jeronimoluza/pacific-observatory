"""
MyMarket.ge (Georgia) -- https://mymarket.ge/.

General classifieds marketplace (part of the TNET group, sibling to
myauto.ge) -- new and secondhand goods across electronics, appliances,
furniture, business equipment, etc.

The public site is a Next.js SSR app; a category listing page
(`/products/<slug>/`) triggers a client-side `POST` to a fully open JSON
API at `https://api.mymarket.ge/api/ka/products` with a plain
`{"CatID": "<id>", "Page": N, "Limit": 28}` body -- no auth, no cookies,
no anti-bot. Verified live 2026-09-06 with curl_cffi (chrome124, headers
limited to Content-Type/Accept/Referer): page 1 and page 2 of CatID=3139
("small kitchen appliances") returned 28 items each, zero id overlap --
genuine pagination.

Each hit already carries a numeric `price` in GEL (`currency_id` is a
site-internal enum; Georgia's own currency is used directly rather than
decoded, matching countries.yaml's GEL default) plus `old_price` for
items on discount -- the spider emits the current `price`, not
`old_price`.

Category ids are discovered from `/api/ka/category?CatID=0`, which returns
a flat `data.categories` list of ~12 top-level nodes (services, rent, home
& garden, appliances, electronics, etc.) rather than a nested tree.
Passing a top-level `CatID` straight to `/products` returns items from the
whole subtree beneath it (verified: CatID=2 "household appliances"
returned washing machines, fridges and a wine cooler in one page) -- no
need to walk the sub-category tree separately.

coicop_classification: classifier -- durables/electronics/furniture mix,
no single COICOP prefix. channel: marketplace (seller-authored titles).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_URL = "https://api.mymarket.ge/api/ka/category?CatID=0"
_PRODUCTS_URL = "https://api.mymarket.ge/api/ka/products"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://mymarket.ge/",
}
PAGE_LIMIT = 28
MAX_PAGES_PER_CAT = 5  # safety cap: ~140 items/category


class MymarketGeSpider(scrapy.Spider):
    name = "mymarket_ge"
    allowed_domains = ["api.mymarket.ge"]
    currency = "GEL"
    language = "ka"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_CATEGORY_URL, headers=_HEADERS, callback=self.parse_categories)

    def parse_categories(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.warning("mymarket_ge: non-JSON category response")
            return
        cats = (data.get("data") or {}).get("categories") or []
        cat_ids = [c.get("cat_id") for c in cats if c.get("cat_id")]
        logger.info(f"mymarket_ge: {len(cat_ids)} top-level categories discovered")
        for cat_id in cat_ids:
            yield self._page_request(cat_id, 1)

    def _page_request(self, cat_id, page):
        body = json.dumps({"CatID": str(cat_id), "Page": page, "Limit": PAGE_LIMIT})
        return scrapy.Request(
            _PRODUCTS_URL,
            method="POST",
            headers=_HEADERS,
            body=body,
            callback=self.parse_page,
            meta={"cat_id": cat_id, "page": page},
        )

    def parse_page(self, response):
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        try:
            data = response.json()
        except ValueError:
            logger.warning(f"mymarket_ge: non-JSON products response cat_id={cat_id}")
            return
        rows = (data.get("data") or {}).get("Prs") or []
        n = 0
        for row in rows:
            item = self._item(row)
            if item:
                n += 1
                yield item
        logger.info(f"mymarket_ge: cat_id={cat_id} page={page} items={n}")

        if len(rows) >= PAGE_LIMIT and page < MAX_PAGES_PER_CAT:
            yield self._page_request(cat_id, page + 1)

    def _item(self, row):
        title = row.get("title")
        price = row.get("price")
        pid = row.get("product_id")
        if not title or price in (None, ""):
            return None
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            return None
        if price_val <= 0:
            return None
        return {
            "product_id": str(pid) if pid else None,
            "product_name": str(title).strip()[:500],
            "price": str(price_val),
            "currency": self.currency,
            "category": str(row.get("cat_id")) if row.get("cat_id") else None,
            "url": f"https://mymarket.ge/product/{pid}" if pid else None,
            "available": True,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
