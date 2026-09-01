"""
Spider for souqly.ly ("Souqly" / سوقلي) -- Libya general online marketplace.
Next.js (App Router) storefront. The rendered HTML ships an embedded RSC
payload, but there is also a clean, open JSON endpoint behind it:

    GET https://souqly.ly/api/products?page=<n>

Verified live 2026-09-01: no auth, no cookies required, plain
`curl_cffi impersonate=chrome124` returns 200. Response shape:
`{"products": [...], "totalProducts": N, "page": p, "productsPerPage": 12,
"totalPages": T}`. `totalProducts` was 16 at probe time (2 pages) -- a
small but real and COMPLETE catalog (product ids run 1..16 with no gaps
across both pages), not a curated homepage rail.

Catalog is general dropship goods (electronics, perfume, books, prayer
accessories, walkie-talkies, jewelry) -- no food/grocery category exists on
the site. `channel: marketplace`, does not count toward the food total.

`salePrice` in the API is a plain numeric string with no thousands
separator or minor-unit encoding (e.g. "170", "115") -- read directly as
LYD, no /1000 or /100 conversion needed. Cross-checked against the
rendered PDP HTML (e.g. product id 1 "gamestick m8" shows "115.00 د.ل" on
page, API returns salePrice="115" -- consistent).
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_API = "https://souqly.ly/api/products"
_PDP_BASE = "https://souqly.ly/product"


class SouqlyLySpider(scrapy.Spider):
    name = "souqly_ly"
    allowed_domains = ["souqly.ly"]
    currency = "LYD"
    language = "ar"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_API}?page=1", callback=self.parse_page, meta={"page": 1}
        )

    def parse_page(self, response):
        try:
            data = response.json()
        except ValueError:
            return
        page = response.meta["page"]
        total_pages = data.get("totalPages") or 1
        scraped_at = datetime.now(timezone.utc).isoformat()
        n = 0
        for row in data.get("products") or []:
            product_id = row.get("id")
            name = row.get("productName")
            price = row.get("salePrice")
            if product_id is None or not name or price in (None, ""):
                continue
            category = (row.get("category") or {}).get("name")
            n += 1
            yield {
                "product_id": str(product_id),
                "product_name": str(name).strip(),
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "available": (row.get("stockQuantity") or 0) > 0,
                "url": f"{_PDP_BASE}/{product_id}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"{self.name}: page {page}/{total_pages}, {n} rows")
        if page < total_pages:
            yield scrapy.Request(
                f"{_API}?page={page + 1}",
                callback=self.parse_page,
                meta={"page": page + 1},
            )
