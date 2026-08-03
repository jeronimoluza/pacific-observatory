"""
Spider for Market Kurly (South Korea) - https://www.kurly.com
Uses the internal JSON API at api.kurly.com directly. No Playwright required.
Scoped to food & beverage categories only (COICOP 01/02).
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class KurlyKrSpider(scrapy.Spider):
    name = "kurly_kr"
    allowed_domains = ["api.kurly.com"]
    currency = "KRW"

    # Food & beverage categories only (COICOP 01/02).
    # Category codes from api.kurly.com/collection/v2/home/sites/market/category-groups
    CATEGORIES = [
        ("907", "채소"),
        ("908", "과일·견과·쌀"),
        ("909", "수산·해산·건어물"),
        ("910", "정육·가공육·달걀"),
        ("911", "국·반찬·메인요리"),
        ("912", "간편식·밀키트·샐러드"),
        ("913", "면·양념·오일"),
        ("914", "생수·음료"),
        ("383", "커피·차"),
        ("249", "간식·과자·떡"),
        ("915", "베이커리"),
        ("018", "유제품"),
        ("722", "와인·위스키·데낄라"),
        ("251", "전통주"),
    ]
    PAGE_SIZE = 20

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def start_requests(self):
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.kurly.com",
            "Referer": "https://www.kurly.com/",
        }
        for cat_id, cat_name in self.CATEGORIES:
            url = (
                f"https://api.kurly.com/collection/v2/home/sites/market"
                f"/product-categories/{cat_id}/products"
                f"?sort_type=4&page=1&per_page={self.PAGE_SIZE}"
            )
            yield scrapy.Request(
                url,
                headers=headers,
                callback=self.parse_category,
                meta={"cat_id": cat_id, "cat_name": cat_name, "page": 1},
            )

    def parse_category(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        data = payload.get("data") or []
        meta_info = (payload.get("meta") or {}).get("pagination") or {}
        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]
        page = response.meta["page"]
        total_pages = meta_info.get("total_pages", 1)

        logger.info(
            f"kurly_kr: cat={cat_name}({cat_id}) page={page}/{total_pages} items={len(data)}"
        )

        for it in data:
            no = it.get("no")
            name = it.get("name")
            price = it.get("discounted_price") or it.get("sales_price")
            if not name or not price:
                continue
            yield {
                "product_id": str(no) if no else None,
                "product_name": name,
                "price": str(price),
                "currency": self.currency,
                "category": cat_name,
                "url": f"https://www.kurly.com/goods/{no}" if no else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        if page < total_pages:
            next_page = page + 1
            next_url = (
                f"https://api.kurly.com/collection/v2/home/sites/market"
                f"/product-categories/{cat_id}/products"
                f"?sort_type=4&page={next_page}&per_page={self.PAGE_SIZE}"
            )
            yield scrapy.Request(
                next_url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Origin": "https://www.kurly.com",
                    "Referer": f"https://www.kurly.com/categories/{cat_id}",
                },
                callback=self.parse_category,
                meta={"cat_id": cat_id, "cat_name": cat_name, "page": next_page},
            )
