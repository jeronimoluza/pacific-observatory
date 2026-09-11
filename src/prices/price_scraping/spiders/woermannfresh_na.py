"""
Woermann Fresh -- https://shop.woermannfresh.com/ (Windhoek, Namibia
supermarket, part of the Woermann Brock group).

Custom e-commerce platform (not Shopify/WooCommerce/Magento despite the
Shopify-style `/products.json` URL -- probed live 2026-09-11 and the
response shape is bespoke: `searchResult.results[].result` objects, not a
Shopify `products` array). Plain, unauthenticated JSON endpoint at
/products.json?page=N.

Enumerability confirmed: page=1 vs page=2 returned fully disjoint product
ID sets (0 overlap), `searchResult.pagination.total_hits.value` = 2857
across `total_pages` = 29 (100 products/page). `store.title` = "Windhoek".

Currency: no explicit currency code in the payload. NAD assumed --
Woermann Brock is a Namibia-only retail group (no ZAR presence), and a
product page's AI-generated description text explicitly reads "Woermann
Fresh, a retailer in Namibia" (same inference pattern as kws_na /
doorstep_na, both of which also lack an explicit currency field).

Page family: API (spider reads /products.json directly). Real PDPs also
exist at /product/<slug> (verified 200, contains the same price) and were
used only to build `url` per item, never fetched by the spider.

Each product carries a `deepest_category.path` (e.g. "drinks/energy-drinks/")
used as `category` -- a genuine breadcrumb, not invented.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://shop.woermannfresh.com"
_LIST_URL = _BASE + "/products.json?page={page}"


class WoermannfreshNaSpider(scrapy.Spider):
    name = "woermannfresh_na"
    allowed_domains = ["shop.woermannfresh.com"]
    currency = "NAD"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(_LIST_URL.format(page=1), callback=self.parse_page)

    def parse_page(self, response):
        try:
            payload = response.json()
        except ValueError:
            logger.warning("woermannfresh_na: non-JSON response at %s", response.url)
            return

        search_result = payload.get("searchResult") or {}
        results = search_result.get("results") or []
        pagination = search_result.get("pagination") or {}
        page = pagination.get("page", 1)
        total_pages = pagination.get("total_pages", page)

        logger.info(
            "woermannfresh_na: page %s/%s -> %s products", page, total_pages, len(results)
        )

        for entry in results:
            record = entry.get("result") or {}
            item = self._item(record)
            if item:
                yield item

        if page < total_pages:
            yield scrapy.Request(
                _LIST_URL.format(page=page + 1), callback=self.parse_page
            )

    def _item(self, p: dict):
        pricing = p.get("product_pricing") or []
        price = pricing[0].get("price") if pricing else p.get("price")
        if price is None:
            return None
        try:
            if float(price) <= 0:
                return None
        except (TypeError, ValueError):
            return None

        name = str(p.get("title") or "").strip()
        name = re.sub(r"\s+", " ", name)
        if not name:
            return None

        slug = p.get("slug")
        deepest_category = p.get("deepest_category") or {}
        category = deepest_category.get("path") or deepest_category.get("title")

        stock = p.get("product_stock") or []
        in_stock = bool(p.get("is_in_stock")) if "is_in_stock" in p else any(
            (s.get("soh") or 0) > 0 for s in stock
        )

        return {
            "product_id": str(p.get("code") or p.get("id") or ""),
            "product_name": name[:500],
            "category": category,
            "price": str(price),
            "currency": self.currency,
            "available": in_stock,
            "url": f"{_BASE}/product/{slug}" if slug else "",
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
