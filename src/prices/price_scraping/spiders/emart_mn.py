"""
Spider for eMart Mongolia (https://emartmall.mn/).

Uses the internal REST API at restapi.emartmall.mn:10443 — bypasses the
Vue.js SPA front-end. Tier 1B (scrapy_api). No Playwright required.
The API is publicly callable with Authorization: Bearer (no token value).
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class EmartMnSpider(scrapy.Spider):
    name = "emart_mn"
    allowed_domains = ["emartmall.mn", "restapi.emartmall.mn"]
    currency = "MNT"

    API_URL = "https://restapi.emartmall.mn:10443/mn/api/search/elastic"
    PAGE_SIZE = 20

    FOOD_CATEGORIES = {
        1: "Fruits & Vegetables",
        2: "Fresh & Dairy",
        740: "Meat products",
        4: "Grocery",
        3: "Candy & Confectionary",
        5: "Beverage & Alcohol",
        29: "Preserved/Canned Foods",
        696: "Frozen products",
        344: "Healthy Food",
    }

    _HEADERS = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer",
        "x-store-x": "null",
        "Origin": "https://emartmall.mn",
        "Referer": "https://emartmall.mn/",
    }

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    def _make_payload(self, cat_id, offset):
        return json.dumps(
            {
                "catId": cat_id,
                "store": None,
                "custId": 0,
                "value": "",
                "attribute": "",
                "color": "",
                "brand": "",
                "promotion": "",
                "minPrice": 0,
                "maxPrice": 0,
                "rowCount": self.PAGE_SIZE,
                "startsWith": offset,
                "orderColumn": "CATID_ASC, ISAVAILABLE_DESC, SALEPERCENT_DESC, RATE_DESC",
                "highlight": False,
            }
        )

    async def start(self):
        for cat_id, cat_name in self.FOOD_CATEGORIES.items():
            yield scrapy.Request(
                self.API_URL,
                method="POST",
                body=self._make_payload(cat_id, 0),
                headers=self._HEADERS,
                callback=self.parse_category,
                meta={"cat_id": cat_id, "cat_name": cat_name, "offset": 0},
                dont_filter=True,
            )

    def parse_category(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        data = payload.get("data") or {}
        hits = data.get("hits") or {}
        total = (hits.get("total") or {}).get("value") or 0
        items = hits.get("hits") or []

        cat_id = response.meta["cat_id"]
        cat_name = response.meta["cat_name"]
        offset = response.meta["offset"]

        logger.info(
            f"emart_mn: catId={cat_id} ({cat_name}) offset={offset} items={len(items)} total={total}"
        )

        for it in items:
            src = it.get("_source") or {}
            price = src.get("currentprice") or src.get("price")
            skucd = src.get("skucd")

            category = cat_name
            parentkey = src.get("parentkey") or ""
            if parentkey and "&&" in parentkey:
                parts = parentkey.split("&&")
                if len(parts) > 2 and parts[2]:
                    category = parts[2]

            if not src.get("title") or price is None:
                continue

            yield {
                "product_id": skucd,
                "product_name": src.get("title"),
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": f"https://emartmall.mn/productdetail/{skucd}" if skucd else None,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        next_offset = offset + self.PAGE_SIZE
        if items and next_offset < total:
            yield scrapy.Request(
                self.API_URL,
                method="POST",
                body=self._make_payload(cat_id, next_offset),
                headers=self._HEADERS,
                callback=self.parse_category,
                meta={"cat_id": cat_id, "cat_name": cat_name, "offset": next_offset},
                dont_filter=True,
            )
