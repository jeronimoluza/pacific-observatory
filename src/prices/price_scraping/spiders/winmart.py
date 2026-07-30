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
    # Category tree fetched from api-crownx.winmart.vn/mt/api/web/v1/category
    # (2026-07-30): the pre-existing list only walked candy/produce/milk and
    # capped every category at 1 page of 20 items, so fresh aisles were
    # either entirely absent (meat, seafood, fruit, leafy veg each live under
    # their own seoName, not folded into cu-qua) or silently truncated
    # (cu-qua alone has 29+ items, thit 29+, trai-cay-tuoi 50+). Added the
    # missing fresh-food leaves; PAGES_PER_CATEGORY/pagination logic below
    # now walks until a short page confirms the category is exhausted.
    CATEGORIES = [
        "banh-keo--c07",
        "cu-qua--c01168",  # tubers / misc produce
        "rau-la--c01167",  # leafy vegetables (01.1.7)
        "trai-cay-tuoi--c01173",  # fresh fruit (01.1.6)
        "thit--c0111",  # meat (01.1.2)
        "hai-san--c0113",  # seafood (01.1.3)
        "sua--c0138",
    ]
    MAX_PAGES_PER_CATEGORY = 30
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
            yield self._category_request(slug, 1, headers)

    def _category_request(self, slug, page, headers):
        url = (
            "https://api-crownx.winmart.vn/it/api/web/v3/item/category"
            f"?orderByDesc=true&pageNumber={page}&pageSize={self.PAGE_SIZE}"
            f"&slug={slug}&storeCode={self.STORE_CODE}"
            f"&storeGroupCode={self.STORE_GROUP_CODE}"
        )
        return scrapy.Request(
            url,
            headers=headers,
            callback=self.parse_category,
            meta={"slug": slug, "page": page, "headers": headers},
        )

    def parse_category(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return
        data = payload.get("data") or {}
        items = data.get("items") or []
        slug = response.meta.get("slug")
        page = response.meta.get("page")
        logger.info(f"winmart: slug={slug} page={page} items={len(items)}")
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
        # A full page means more may follow; a short/empty page means the
        # category is exhausted. Capped to avoid runaway pagination.
        if len(items) == self.PAGE_SIZE and page < self.MAX_PAGES_PER_CATEGORY:
            yield self._category_request(slug, page + 1, response.meta["headers"])
