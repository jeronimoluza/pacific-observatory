"""
Spider for PharmEasy (India pharmacy) - https://pharmeasy.in/

Uses the internal JSON API at pharmeasy.in/api/otc/getCategoryProducts.
No auth required; just Origin/Referer headers. Paginated 20/page per category.
Categories enumerated via /api/home/fetchCategories — 16 OTC categories.
"""

import json
import logging

import scrapy

logger = logging.getLogger(__name__)


class PharmeasySpider(scrapy.Spider):
    name = "pharmeasy"
    allowed_domains = ["pharmeasy.in"]
    currency = "INR"
    page_size = 20
    api_url = "https://pharmeasy.in/api/otc/getCategoryProducts"

    # Top-level OTC category IDs scraped from /api/home/fetchCategories.
    CATEGORIES = [
        9297,   # Must Haves
        623,    # Vitamin Store
        877,    # Personal Care
        575,    # Sexual Wellness
        16709,  # Summer Store
        16819,  # Pet Care
        648,    # Health Food and Drinks
        145,    # Diabetes Essentials
        765,    # Ayurvedic Care
        838,    # Mother and Baby Care
        750,    # Mobility & Elderly Care
        12931,  # Sports Nutrition
        717,    # Healthcare Devices
        93,     # Skin Care
        693,    # Health Concerns
        15393,  # Explore More
    ]
    MAX_PAGES_PER_CATEGORY = 30  # 30 * 20 = 600 items cap per cat

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS": 4,
    }

    def start_requests(self):
        headers = {
            "Accept": "application/json",
            "Origin": "https://pharmeasy.in",
            "Referer": "https://pharmeasy.in/",
        }
        for cat_id in self.CATEGORIES:
            yield scrapy.Request(
                f"{self.api_url}?categoryId={cat_id}&page=1",
                headers=headers,
                callback=self.parse,
                meta={"cat_id": cat_id, "page": 1},
            )

    def parse(self, response):
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for {response.url}")
            return

        data = payload.get("data") or {}
        products = data.get("products") or []
        cat_id = response.meta["cat_id"]
        page = response.meta["page"]
        logger.info(f"pharmeasy: cat={cat_id} page={page} products={len(products)}")

        scraped_at = response.headers.get("Date", b"").decode("utf-8")
        for p in products:
            price = p.get("salePriceDecimal") or p.get("mrpDecimal")
            if not price:
                continue
            slug = p.get("slug")
            yield {
                "product_id": str(p.get("productId")) if p.get("productId") else None,
                "product_name": p.get("name"),
                "price": price,
                "currency": self.currency,
                "category": str(cat_id),
                "url": f"https://pharmeasy.in/online-medicine-order/{slug}" if slug else None,
                "scraped_at": scraped_at,
            }

        if products and page < self.MAX_PAGES_PER_CATEGORY:
            yield scrapy.Request(
                f"{self.api_url}?categoryId={cat_id}&page={page + 1}",
                headers={
                    "Accept": "application/json",
                    "Origin": "https://pharmeasy.in",
                    "Referer": "https://pharmeasy.in/",
                },
                callback=self.parse,
                meta={"cat_id": cat_id, "page": page + 1},
            )
