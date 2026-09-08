"""
Spider for Megasuper (Costa Rica) - megasuper.com

Homepage is a bare Next.js shell with no product data in raw HTML (all
category/product data is client-fetched). Recovered via Playwright network
trace: the front-end calls a shared LatAm grocery-commerce backend
("Instaleap"/"Moira Engine") at nextgentheadless.instaleap.io/api/v3
(GraphQL, Apollo Server, introspection disabled), authenticated with a
`dpl-api-key` header that is shipped in every visitor's page load (a public
per-tenant key, not a secret). No Playwright required to scrape.

The exact query shape (`getProductsByCategoryInput` object wrapper,
`currentPage` for pagination) had to be found by trial against the live
schema -- the query text embedded in the site's own JS bundle
(GetProductsByCategory with a `categoryId` arg) is STALE and does not match
what the live server actually accepts; do not copy it verbatim.

Top-level category references come from GetCategoryTree (18 categories,
e.g. "01" ABARROTES / groceries, "10" FRUTAS Y VERDURAS / produce, "13"
LACTEOS Y HUEVOS / dairy+eggs) -- spans most of COICOP divisions 01-13.
"""

import logging

import scrapy
from scrapy.http import JsonRequest

logger = logging.getLogger(__name__)

_API_URL = "https://nextgentheadless.instaleap.io/api/v3"
_API_KEY = "09e9a997-5c41-4460-8fe7-3fa37f9774f1"
_CLIENT_ID = "MEGASUPER"
_STORE_REF = "M102"

_CATEGORIES = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "10", "11", "12", "13", "14", "15", "16", "17", "18",
]

_PRODUCTS_QUERY = """
{ getProductsByCategory(getProductsByCategoryInput: {
    clientId: "%s", storeReference: "%s", categoryReference: "%s", currentPage: %d
  }) {
    pagination { page pages }
    category { name reference products { name price sku ean unit brand } }
  }
}
"""


class MegasuperCrSpider(scrapy.Spider):
    name = "megasuper_cr"
    allowed_domains = ["nextgentheadless.instaleap.io"]
    currency = "CRC"

    MAX_PAGES_PER_CATEGORY = 30  # safety cap; some categories run to ~99 pages

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "dpl-api-key": _API_KEY,
        }

    def _request(self, category_ref, page):
        query = _PRODUCTS_QUERY % (_CLIENT_ID, _STORE_REF, category_ref, page)
        return JsonRequest(
            _API_URL,
            method="POST",
            headers=self._headers(),
            data=[{"query": query}],
            callback=self.parse_page,
            meta={"category_ref": category_ref, "page": page},
            dont_filter=True,
        )

    def start_requests(self):
        for cat in _CATEGORIES:
            yield self._request(cat, 1)

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        payload = (data[0] if isinstance(data, list) else data).get("data") or {}
        result = payload.get("getProductsByCategory") or {}
        category = result.get("category") or {}
        products = category.get("products") or []
        pagination = result.get("pagination") or {}
        category_ref = response.meta["category_ref"]
        page = response.meta["page"]

        logger.info(
            f"megasuper_cr: category={category_ref} page={page} "
            f"products={len(products)} pages={pagination.get('pages')}"
        )

        for p in products:
            name = p.get("name")
            price = p.get("price")
            sku = p.get("sku")
            if not name or price is None or not sku:
                continue
            yield {
                "product_id": sku,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category.get("name"),
                "url": f"https://www.megasuper.com/?sku={sku}#{sku}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        total_pages = pagination.get("pages") or 0
        if products and page < total_pages and page < self.MAX_PAGES_PER_CATEGORY:
            yield self._request(category_ref, page + 1)
