"""
Spider for Choithrams UAE - www.choithrams.com

Angular Universal SPA shell (no product data server-rendered, "product/:slug"
client route). The homepage's own bundle calls a same-origin, unauthenticated
JSON API under /api/websf/ (found via a Playwright network-capture pass on
2026-09-01 -- "Playwright to discover, plain HTTP to scrape" -- the front
page is not WAF-protected, so the API works with plain curl_cffi too, no
special headers needed):

  - /api/websf/category/getall?sort_by=Position&target_image_size=313
    returns the full 3-level category tree (15 top-level nodes: Household,
    Breakfast & Snacking, Cooking & Ingredients, Health & Beauty, Home &
    Life, Frozen, Beverages, Fresh, Baby, Non Halal, Kiosk, Festives &
    Events, Pets, Food To Go, Fashion & Beauty).
  - /api/websf/product/category/getall?category_ids=<id>&page_index=<n>&
    page_size=100&sort_by=Position returns paginated products for that
    category id -- confirmed it accepts TOP-LEVEL ids directly (aggregates
    all descendants), so this spider walks only the 15 top-level ids
    rather than every leaf, at page_size=100 (confirmed pagination
    advances with zero id overlap between page 1 and page 2 of a 1,543-row
    category).

Each product record carries its own (finer-grained) category_id, which is
mapped back to a human breadcrumb via a category_id -> breadcrumb index
built by flattening the full tree fetched at start(); this is more precise
than tagging every row with the top-level query id.

Currency: AED, hardcoded. og:locale on the homepage is en_AE and the meta
description advertises "fast delivery across the UAE" -- Choithrams is a
Dubai-headquartered UAE supermarket chain; there is no other-country
variant of this domain. offer_price is the field to emit (was_price is the
pre-discount strikethrough price, 0.0 when there is no discount).

7,365 of ~10,516 total product listings (measured 2026-09-01, records_total
summed across the 15 top categories) sit under food-relevant top
categories (Breakfast & Snacking, Cooking & Ingredients, Frozen, Beverages,
Fresh, Baby, Kiosk, Food To Go) -- roughly 70% by category count, a
genuine grocery catalogue, not a supermarket-adjacent sideline.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_CATEGORY_URL = (
    "https://www.choithrams.com/api/websf/category/getall"
    "?sort_by=Position&target_image_size=313"
)
_PRODUCTS_URL = (
    "https://www.choithrams.com/api/websf/product/category/getall"
    "?category_ids={cid}&page_index={page}&page_size=100&sort_by=Position"
)


def _flatten_categories(nodes, out):
    for node in nodes or []:
        cid = node.get("category_id")
        breadcrumb = node.get("breadcrumb") or node.get("category_name")
        if cid is not None and breadcrumb:
            out[cid] = breadcrumb
        _flatten_categories(node.get("sub_categories"), out)


class ChoithramsAeSpider(scrapy.Spider):
    name = "choithrams_ae"
    allowed_domains = ["choithrams.com"]
    currency = "AED"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_CATEGORY_URL, callback=self.parse_categories)

    def parse_categories(self, response):
        data = response.json().get("data") or []
        cat_map: dict = {}
        _flatten_categories(data, cat_map)
        self._cat_map = cat_map

        top_ids = [node.get("category_id") for node in data if node.get("category_id")]
        logger.info("choithrams_ae: %d top-level categories", len(top_ids))
        for cid in top_ids:
            yield scrapy.Request(
                _PRODUCTS_URL.format(cid=cid, page=1),
                callback=self.parse_products,
                meta={"cid": cid, "page": 1},
            )

    def parse_products(self, response):
        cid = response.meta["cid"]
        page = response.meta["page"]
        payload = response.json().get("data") or []
        if not payload:
            return
        products_block = payload[0].get("products") or {}
        records = products_block.get("records") or []
        records_total = products_block.get("records_total") or 0
        logger.info(
            "choithrams_ae: category=%s page=%d records=%d total=%d",
            cid,
            page,
            len(records),
            records_total,
        )
        for p in records:
            item = self._item(p)
            if item:
                yield item

        if page * 100 < records_total:
            yield scrapy.Request(
                _PRODUCTS_URL.format(cid=cid, page=page + 1),
                callback=self.parse_products,
                meta={"cid": cid, "page": page + 1},
            )

    def _item(self, p: dict):
        price = p.get("offer_price")
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        name = str(p.get("product_name") or "").strip()
        if not name:
            return None
        product_id = p.get("product_id")
        if product_id is None:
            return None
        category = self._cat_map.get(p.get("category_id"))

        return {
            "product_id": str(product_id),
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": bool(p.get("stock_quantity") or 0),
            "url": f"https://www.choithrams.com/product/{product_id}",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
