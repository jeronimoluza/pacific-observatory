"""
Spider for Freshmart (Peru) -- https://freshmart.pe/.

Organic/specialty grocer, bespoke jQuery/React front end (no known
platform). Front-end JS (`/static/main.js`) calls a wide-open, unauthenticated
JSON search API at `POST /api/search/product` with
`action=shopping_search_product`, `q=""` (empty query returns the whole
catalog), `id_comercio=4`, `limit=unlimited`, `type=normal`,
`is_express=0`, paginated via `page=N` (20 items/page). Confirmed live
2026-09-06: page 0/1/2 all return 20 distinct product ids; the endpoint
returns `{"status": true, "data": []}` once pages run out (probed to
page 500).

Category ids on each product (`id_categoria_principal`,
`id_categoria_secundaria`) do NOT match the id-space used by the site's
own `/categoria/advanced-menu` tree (spot-checked: product 4237's
id_categoria_secundaria=329 has no match in the menu's leaf ids) --
category is left null rather than guessed.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API_URL = "https://freshmart.pe/api/search/product"
MAX_PAGES = 400  # safety cap; catalog observed to end well before this


class FreshmartPeSpider(scrapy.Spider):
    name = "freshmart_pe"
    allowed_domains = ["freshmart.pe"]
    currency = "PEN"
    language = "es"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def _form(self, page: int) -> dict:
        return {
            "action": "shopping_search_product",
            "q": "",
            "page": str(page),
            "order": "",
            "id_comercio": "4",
            "limit": "unlimited",
            "type": "normal",
            "is_express": "0",
        }

    async def start(self):
        yield scrapy.FormRequest(
            _API_URL,
            formdata=self._form(0),
            callback=self.parse_page,
            meta={"page": 0},
        )

    def parse_page(self, response):
        page = response.meta["page"]
        try:
            payload = response.json()
        except ValueError:
            logger.warning("freshmart_pe: bad JSON on page %d", page)
            return
        rows = payload.get("data") or []
        logger.info("freshmart_pe: page %d -> %d rows", page, len(rows))
        for row in rows:
            item = self._item(row)
            if item:
                yield item

        if rows and page < MAX_PAGES:
            nxt = page + 1
            yield scrapy.FormRequest(
                _API_URL,
                formdata=self._form(nxt),
                callback=self.parse_page,
                meta={"page": nxt},
            )

    def _item(self, row: dict):
        name = (row.get("name") or "").strip()
        product_id = str(row.get("id") or row.get("sku") or "")
        price = row.get("nuevo_precio")
        if not price or price in ("0.00", "0"):
            price = row.get("price")
        if not name or not product_id or not price or str(price) in ("0", "0.00"):
            return None
        return {
            "product_id": product_id,
            "product_name": name.replace("\n", " ").strip()[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": bool(row.get("stock", 0)),
            "url": row.get("link") or "https://freshmart.pe/",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
