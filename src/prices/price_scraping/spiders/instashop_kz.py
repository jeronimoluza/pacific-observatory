"""
Spider for InstaShop (Kazakhstan) -- https://instashop.kz/.

Quick-commerce aggregator (per AI_NOTES: 51+ stores in Almaty alone,
including bazaar/traditional-market verticals). The `/en/catalog` page
renders a fixed 25-item grid server-side with no working pagination
(`?page=2` returned the identical 25 items in testing) -- the real
pagination is client-side, hitting a clean unauthenticated JSON API
found via Playwright network-capture (2026-09-06):

  GET /api/catalog/categories?lang=ru
      -> [{"id","name","subcategories":[{"id","name",...}]}] -- 51
      top-level categories / 239 leaf subcategories confirmed live.
      Products only attach at the LEAF level: querying a top-level
      category id directly returns total=0 (confirmed live on "Снеки,
      закуски и шоколад") -- the crawl must walk leaf ids (top-level
      categories with no subcategories count as their own leaf).

  GET /api/catalog/products?categoryId=<leaf_id>&lang=ru&offset=<n>&limit=100
      -> {"total","count","offset","limit","items":[{"productId","name",
      "sku","inStock","minPrice","minPriceFormated"}]} -- standard
      offset/limit pagination, confirmed live (10,055 products under one
      leaf category, limit=100 accepted).

This reads the aggregator's OWN catalog (not a per-seller directory) --
per the skill's marketplace guidance the seller directory is normally
preferred, but instashop's storefront is genuinely unified (one cart
across "51+ stores... explicitly 'prices as in store'" per AI_NOTES),
not a directory of independently branded shops, so there is no separate
first-party retailer list to onboard instead.

Confirmed live 2026-09-06: leaf category a671469f-280c-4061-a167-
7a724701732f, product "Тан классический 1,0 л." (Tan/ayran drink)
minPrice=... KZT (plain integer, no minor-unit scaling). Some items carry
minPrice=0 with an empty minPriceFormated (out-of-stock/no-offer
placeholders) -- dropped.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://instashop.kz/api/catalog"
_PAGE_LIMIT = 100
MAX_PAGES_PER_CATEGORY = 200  # safety cap; largest leaf seen was 10,055/100=101 pages


class InstashopKzSpider(scrapy.Spider):
    name = "instashop_kz"
    allowed_domains = ["instashop.kz"]
    currency = "KZT"
    language = "ru"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.3,
        "DOWNLOAD_TIMEOUT": 15,
        "RETRY_TIMES": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/categories?lang=ru", callback=self.parse_categories
        )

    def parse_categories(self, response):
        try:
            categories = response.json()
        except ValueError:
            logger.error("instashop_kz: categories response not JSON")
            return
        leaf_ids = []
        for c in categories:
            subs = c.get("subcategories") or []
            if subs:
                leaf_ids.extend(s["id"] for s in subs if s.get("id"))
            elif c.get("id"):
                leaf_ids.append(c["id"])
        logger.info(f"instashop_kz: {len(leaf_ids)} leaf categories")
        for cat_id in leaf_ids:
            yield self._page_request(cat_id, 0)

    def _page_request(self, cat_id: str, offset: int):
        url = (
            f"{_BASE}/products?categoryId={cat_id}&lang=ru"
            f"&offset={offset}&limit={_PAGE_LIMIT}"
        )
        return scrapy.Request(
            url,
            callback=self.parse_page,
            meta={"cat_id": cat_id, "offset": offset},
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        items = data.get("items") or []
        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in items:
            item = self._item(p, scraped_at)
            if item:
                yield item

        offset = response.meta["offset"]
        total = data.get("total", 0)
        next_offset = offset + _PAGE_LIMIT
        if items and next_offset < total and next_offset // _PAGE_LIMIT < MAX_PAGES_PER_CATEGORY:
            yield self._page_request(response.meta["cat_id"], next_offset)

    def _item(self, p: dict, scraped_at: str):
        name = (p.get("name") or "").strip()
        price = p.get("minPrice")
        if not name or price is None:
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        product_id = str(p.get("productId") or p.get("sku") or "")
        return {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("inStock", True)),
            # The list API does not return a slug/canonical url, only
            # productId -- use a per-product url keyed on the id so the
            # DuplicationPipeline's url-based dedup doesn't collapse every
            # row into one (it dedups on item['url'], not product_id; a
            # constant placeholder url silently dropped all but the first
            # item in testing, confirmed live 2026-09-06).
            "url": f"https://instashop.kz/ru/product/{product_id}",
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
