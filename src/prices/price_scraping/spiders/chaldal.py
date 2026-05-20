"""
Spider for Chaldal (Bangladesh, online grocery) - https://chaldal.com/

Uses the catalog.chaldal.com /searchPersonalized POST endpoint with a static
apiKey scraped from the SPA. No auth, paginated. 50 items per page.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class ChaldalSpider(scrapy.Spider):
    name = "chaldal"
    allowed_domains = ["catalog.chaldal.com", "chaldal.com"]
    currency = "BDT"
    api_url = "https://catalog.chaldal.com/searchPersonalized"
    page_size = 50

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 4,
    }

    BODY = {
        "apiKey": "e964fc2d51064efa97e94db7c64bf3d044279d4ed0ad4bdd9dce89fecc9156f0",
        "storeId": 1,
        "warehouseId": 8,
        "pageSize": page_size,
        "currentPageIndex": 0,
        "metropolitanAreaId": 1,
        "query": "",
        "productVariantId": -1,
        "bundleId": {"case": "None"},
        "canSeeOutOfStock": "false",
        "filters": [],
        "maxOutOfStockCount": {"case": "Some", "fields": [0]},
        "shouldShowAlternateProductsForAllOutOfStock": {
            "case": "Some",
            "fields": ["true"],
        },
        "customerGuid": {"case": "None"},
        "deliveryAreaId": {"case": "None"},
        "shouldShowCategoryBasedRecommendations": {"case": "None"},
    }

    def start_requests(self):
        yield self._page_request(0)

    def _page_request(self, page_index):
        body = dict(self.BODY)
        body["currentPageIndex"] = page_index
        return scrapy.Request(
            self.api_url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://chaldal.com",
                "Referer": "https://chaldal.com/",
                "Accept": "application/json",
            },
            body=json.dumps(body),
            callback=self.parse,
            meta={"page": page_index},
            dont_filter=True,
        )

    def parse(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        hits = data.get("hits", [])
        page = response.meta.get("page", 0)
        nb_pages = data.get("nbPages", 0)
        logger.info(
            f"chaldal: page={page}/{nb_pages} hits={len(hits)} total_nbHits={data.get('nbHits')}"
        )

        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        for it in hits:
            price = it.get("price") if it.get("price") is not None else it.get("mrp")
            if price is None:
                continue
            cats = it.get("categories") or []
            category = ",".join(str(c) for c in cats) if cats else None
            slug = it.get("slug")
            yield {
                "product_id": str(it.get("objectID"))
                if it.get("objectID") is not None
                else None,
                "product_name": it.get("name") or it.get("nameWithoutSubText"),
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"https://chaldal.com/p/{slug}" if slug else None,
                "scraped_at": scraped_at,
            }

        # paginate
        if hits and page + 1 < nb_pages:
            yield self._page_request(page + 1)
