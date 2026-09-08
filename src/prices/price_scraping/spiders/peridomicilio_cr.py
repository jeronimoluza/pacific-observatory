"""
Spider for Peridomicilio (Costa Rica) - peridomicilio.com

Same platform and recovery path as megasuper_cr (see that spider's
docstring): a bare Next.js shell backed by the shared LatAm "Instaleap"/
"Moira Engine" GraphQL API at nextgentheadless.instaleap.io/api/v3,
authenticated with a tenant-specific `dpl-api-key` shipped client-side
(public, not a secret). Different clientId/storeReference/api-key than
megasuper_cr, otherwise identical query shape
(`getProductsByCategoryInput` wrapper, `currentPage` pagination).

24 top-level categories from GetCategoryTree span most of COICOP divisions
01-13 (produce, meat/fish, pantry, dairy/eggs, bakery, deli/cheese,
frozen, beverages, snacks, personal care, pharmacy, household, paper
goods, baby, pet, cigarettes, sports, bazaar, home).
"""

import logging

import scrapy
from scrapy.http import JsonRequest

logger = logging.getLogger(__name__)

_API_URL = "https://nextgentheadless.instaleap.io/api/v3"
_API_KEY = "19781483-0ae5-4577-a05d-cca0a01cb2d0"
_CLIENT_ID = "PERI_DOMICILIOS"
_STORE_REF = "133"

_CATEGORIES = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10",
    "F11", "F12", "F13", "F14", "F15", "F16", "F17", "F19", "F21", "F23",
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


class PeridomicilioCrSpider(scrapy.Spider):
    name = "peridomicilio_cr"
    allowed_domains = ["nextgentheadless.instaleap.io"]
    currency = "CRC"

    MAX_PAGES_PER_CATEGORY = 30

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
            f"peridomicilio_cr: category={category_ref} page={page} "
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
                "url": f"https://www.peridomicilio.com/?sku={sku}#{sku}",
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        total_pages = pagination.get("pages") or 0
        if products and page < total_pages and page < self.MAX_PAGES_PER_CATEGORY:
            yield self._request(category_ref, page + 1)
