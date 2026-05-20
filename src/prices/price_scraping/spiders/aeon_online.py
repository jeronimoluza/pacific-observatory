"""
Spider for scraping Aeon Online (Cambodia) - https://aeononlineshopping.com/

The site was rewritten in 2026 from a custom JSON API
(GET /api/store/{slug}) to a Next.js app whose client calls a proxied
backend at GET /api/proxy/stores/{slug}/products.

Strategy:
1. For each known Aeon / MaxValu store slug, hit
   /api/proxy/stores/{slug}/products?page=N&limit=100 with the
   x-currency: KHR header so prices come back as Cambodian Riel
   (matching the previous spider's output).
2. Paginate while products.meta.hasNextPage is true.
3. Yield one item per product with a unique URL
   (https://aeononlineshopping.com/product/{slug}/{id}).
"""

import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class AeonOnlineSpider(scrapy.Spider):
    name = "aeon_online"
    allowed_domains = ["aeononlineshopping.com"]
    currency = "KHR"

    STORE_SLUGS = [
        "aeon1-aeon-phnom-penh",
        "aeon2-aeon-sen-sok",
        "aeon3-aeon-mean-chey",
        "maxvalu-toul-kork",
        "maxvalu-boeung-kak",
        "aeon1-aeon-food-phnom-penh",
        "aeon2-aeon-food-sen-sok",
        "aeon3-aeon-food-mean-chey",
        "aeon3-fashion-beauty",
        "maxvalu-tuek-thla",
        "maxvalu-express-reoussey-keo-598",
        "maxvalu-tonle-bassac-monivong",
    ]

    PRODUCTS_API = (
        "https://aeononlineshopping.com/api/proxy/stores/{slug}/products"
        "?page={page}&limit={limit}"
    )
    PAGE_LIMIT = 100  # API rejects limit > 100.

    REQUEST_HEADERS = {
        "Accept": "application/json",
        "x-currency": "KHR",
    }

    def start_requests(self):
        for slug in self.STORE_SLUGS:
            yield self._page_request(slug, page=1)

    def _page_request(self, slug, page):
        url = self.PRODUCTS_API.format(slug=slug, page=page, limit=self.PAGE_LIMIT)
        return scrapy.Request(
            url,
            callback=self.parse_products,
            meta={"slug": slug, "page": page},
            headers=self.REQUEST_HEADERS,
        )

    def parse_products(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error("aeon_online: non-JSON response for %s p%d", slug, page)
            return

        products = payload.get("products") or {}
        data = products.get("data") or []
        meta = products.get("meta") or {}

        scraped_at = datetime.now(timezone.utc).isoformat()
        for p in data:
            product_id = p.get("id")
            if product_id is None or not p.get("name"):
                continue
            yield {
                "product_id": str(product_id),
                "product_name": p.get("name"),
                "price": p.get("salePrice"),
                "price_before_discount": p.get("fullPriceBeforeDiscount"),
                "currency": self.currency,
                "barcode": p.get("barcode"),
                "image": p.get("image"),
                "is_out_of_stock": bool(p.get("isOutOfStock")),
                "quantity": p.get("quantity"),
                "store_slug": slug,
                "url": f"https://aeononlineshopping.com/product/{slug}/{product_id}",
                "scraped_at": scraped_at,
            }

        if meta.get("hasNextPage"):
            yield self._page_request(slug, page=page + 1)
