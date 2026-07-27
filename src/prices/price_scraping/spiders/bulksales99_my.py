"""
Spider for 99 Bulksales (Malaysia) - 99bulksales.my, the e-commerce arm of
99 Speedmart.

Server-rendered category listing pages carry product name + price in the raw
HTML (no JS needed). We enumerate the food & beverage category slugs and read
the product cards directly. Bulk retailer: names encode pack sizes
(e.g. "100 PLUS AKTIF 24*500ML"), left intact for downstream unit-value parsing.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.99bulksales.my"
_CAT_URL = _BASE + "/shop/category-products?category={slug}"

_CATEGORIES = [
    "groceries",
    "drinks",
    "instant-drink",
    "coffee-tea",
    "bread",
    "breakfast-cereals",
    "canned-food",
    "cooking-oils",
    "chips-nuts",
    "chocolate-candy",
    "confectionariesbiscuits",
    "alcohol",
]


class Bulksales99MySpider(scrapy.Spider):
    name = "bulksales99_my"
    allowed_domains = ["99bulksales.my"]
    currency = "MYR"
    language = "en"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in _CATEGORIES:
            yield scrapy.Request(
                _CAT_URL.format(slug=slug),
                callback=self.parse_category,
                meta={"category": slug},
            )

    def parse_category(self, response):
        slug = response.meta["category"]
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for a in response.css('a[href*="/shop/product/"]'):
            name = a.css(".prod-nm::text").get()
            price = a.css(".prod-price::text").get()
            if not name or not price:
                continue
            name = name.strip()
            price = price.strip()
            if not name or not price:
                continue
            count += 1
            yield {
                "product_id": None,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": slug,
                "url": a.attrib.get("href"),
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info("bulksales99_my: category=%s products=%d", slug, count)

    def errback(self, failure):
        logger.error(
            "bulksales99_my: request failed %s — %r", failure.request.url, failure.value
        )
