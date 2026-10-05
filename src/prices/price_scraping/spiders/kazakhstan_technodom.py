"""Scrape current consumer-electronics prices from Technodom Kazakhstan."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.parse import urljoin

import scrapy


logger = logging.getLogger(__name__)

BASE_URL = "https://www.technodom.kz"
CATEGORY_URL = (
    f"{BASE_URL}/catalog/smartfony-i-gadzhety/"
    "smartfony-i-telefony/smartfony"
)
MAX_PAGES = 20


def parse_product(product: dict, scraped_at: str):
    sku = str(product.get("sku") or "").strip()
    name = " ".join(unescape(str(product.get("title") or "")).split())
    uri = str(product.get("uri") or "").strip()
    try:
        price = Decimal(str(product.get("price")))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not sku or not name or not uri or price <= 0:
        return None
    categories = product.get("categoriesRu") or product.get("categories") or []
    return {
        "product_id": sku,
        "product_name": name[:500],
        "category": categories[0] if categories else "smartphones",
        "price": format(price, "f"),
        "currency": "KZT",
        "country": "Kazakhstan",
        "sector": "consumer_goods",
        "available": True,
        "url": urljoin(BASE_URL, f"/p/{uri}"),
        "language": "ru",
        "scraped_at_utc": scraped_at,
    }


class KazakhstanTechnodomSpider(scrapy.Spider):
    name = "kazakhstan_technodom"
    allowed_domains = ["technodom.kz", "www.technodom.kz"]
    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 1.0,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(CATEGORY_URL, callback=self.parse, meta={"page": 1})

    def parse(self, response):
        raw = response.css("script#__NEXT_DATA__::text").get()
        if not raw:
            logger.warning("%s: no __NEXT_DATA__ at %s", self.name, response.url)
            return
        try:
            product_list = json.loads(raw)["props"]["pageProps"]["initialState"][
                "productList"
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("%s: malformed product state at %s", self.name, response.url)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        products = product_list.get("items") or []
        for product in products:
            item = parse_product(product, scraped_at)
            if item:
                yield item

        pagination = product_list.get("paginationData") or {}
        page = int(pagination.get("currentPage") or response.meta.get("page", 1))
        total_pages = min(int(pagination.get("totalPages") or page), MAX_PAGES)
        logger.info("%s: page=%d rows=%d total_pages=%d", self.name, page, len(products), total_pages)
        if products and page < total_pages:
            next_page = page + 1
            yield scrapy.Request(
                f"{CATEGORY_URL}?page={next_page}",
                callback=self.parse,
                meta={"page": next_page},
            )
