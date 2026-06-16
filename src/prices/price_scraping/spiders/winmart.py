"""
Spider for WinMart Vietnam.

Uses the internal JSON API at api-crownx.winmart.vn directly — bypasses the
SPA front-end. No Playwright required; the API serves clean records with
itemNo, name, price, salePrice, barcode, categoryName, and seoName.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class WinmartSpider(scrapy.Spider):
    name = "winmart"
    allowed_domains = ["api-crownx.winmart.vn"]
    currency = "VND"

    STORE_CODE = "1535"
    STORE_GROUP_CODE = "1998"
    CATEGORIES = [
        "banh-keo--c07",
        "cu-qua--c01168",
        "sua--c0138",
    ]
    PAGES_PER_CATEGORY = 1
    PAGE_SIZE = 20

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    async def start(self):
        headers = {
            "Accept": "application/json",
            "Origin": "https://winmart.vn",
            "Referer": "https://winmart.vn/",
        }
        for slug in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                url = (
                    "https://api-crownx.winmart.vn/it/api/web/v3/item/category"
                    f"?orderByDesc=true&pageNumber={page}&pageSize={self.PAGE_SIZE}"
                    f"&slug={slug}&storeCode={self.STORE_CODE}"
                    f"&storeGroupCode={self.STORE_GROUP_CODE}"
                )
                yield scrapy.Request(
                    url,
                    headers=headers,
                    callback=self.parse_category,
                    meta={"slug": slug, "page": page},
                )

    def parse_category(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return
        data = payload.get("data") or {}
        items = data.get("items") or []
        logger.info(
            f"winmart: slug={response.meta.get('slug')} "
            f"page={response.meta.get('page')} items={len(items)}"
        )
        for it in items:
            seo = it.get("seoName")
            yield {
                "product_id": it.get("itemNo"),
                "product_name": it.get("name") or it.get("shortDescription"),
                "price": it.get("salePrice") or it.get("price"),
                "currency": self.currency,
                "category": it.get("categoryName"),
                "url": f"https://winmart.vn/{seo}" if seo else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
