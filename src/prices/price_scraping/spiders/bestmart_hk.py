"""
Spider for Best Mart 360 / 優品360 (Hong Kong) - bestmart360.com.

Category listing pages are server-rendered with product name + price co-located
in each card (no JS needed). The PDP is JS-routed (pushState), so we extract at
listing granularity and rebuild the product URL from its data-product-id.
The price string keeps its pack suffix (e.g. "$168.0 / 2 件") for downstream
unit-value parsing.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://www.bestmart360.com"
_CAT_URL = _BASE + "/cat/{slug}"

_CATEGORIES = [
    "Beverages",
    "Wine",
    "Biscuits-Snacks-Seaweed",
    "Cereals-Noodles-Rice",
    "Chocolate-Candies-Sweets",
    "Frozen-Food",
    "Nuts-Dried-Fruit",
    "Oils-Canned-food-seasoning",
]


class BestmartHkSpider(scrapy.Spider):
    name = "bestmart_hk"
    allowed_domains = ["bestmart360.com"]
    currency = "HKD"
    language = "zh"

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
        for card in response.css("div.product_li"):
            name = card.css("div.txt::text").get()
            price_parts = card.css("div.new_price ::text").getall()
            price = re.sub(r"\s+", " ", "".join(price_parts)).strip()
            product_id = card.css("[data-product-id]::attr(data-product-id)").get()
            if not name or not price:
                continue
            name = name.strip()
            if not name:
                continue
            count += 1
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": slug,
                "url": f"{_BASE}/cat?product_id={product_id}"
                if product_id
                else response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info("bestmart_hk: category=%s products=%d", slug, count)

    def errback(self, failure):
        logger.error(
            "bestmart_hk: request failed %s — %r", failure.request.url, failure.value
        )
