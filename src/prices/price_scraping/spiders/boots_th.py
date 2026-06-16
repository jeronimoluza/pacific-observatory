"""
Spider for scraping Boots Thailand - https://store.boots.co.th/
Extracts product information including prices, categories, and URLs.

Uses the Boots Thailand REST API directly to fetch product data.
API endpoint: /api/v1/products/web?locale=en&size=50&page={page}
"""

import scrapy
import logging
import json

logger = logging.getLogger(__name__)

API_BASE = "https://store.boots.co.th/api/v1/products/web"
PAGE_SIZE = 50
MAX_PAGES = 100


class BootsThSpider(scrapy.Spider):
    """
    API-based spider for Boots Thailand.
    Fetches product data from REST API and paginates through results.
    """

    name = "boots_th"
    allowed_domains = ["store.boots.co.th"]
    currency = "THB"

    async def start(self):
        url = f"{API_BASE}?locale=en&size={PAGE_SIZE}&page=1"
        yield scrapy.Request(
            url,
            callback=self.parse_api,
            meta={"page": 1},
            headers={"Accept": "application/json"},
        )

    def parse_api(self, response):
        """Parse API JSON response and extract product data."""
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {response.url}")
            return

        entities = data.get("entities", [])
        page_info = data.get("page_information", {})
        current_page = response.meta.get("page", 1)
        total_pages = page_info.get("number_of_page", 1)

        logger.info(f"Page {current_page}/{total_pages}: {len(entities)} products")

        for product in entities:
            product_name = product.get("product_name_en") or product.get("name")
            price = product.get("price")
            category = product.get("category_name")
            item_code = product.get("item_code")

            if not product_name or price is None:
                continue

            yield {
                "product_name": product_name.strip(),
                "category": category,
                "price": str(price),
                "currency": self.currency,
                "url": f"https://store.boots.co.th/ecommerce/{item_code}"
                if item_code
                else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        # Paginate
        if current_page < min(total_pages, MAX_PAGES) and len(entities) > 0:
            next_page = current_page + 1
            next_url = f"{API_BASE}?locale=en&size={PAGE_SIZE}&page={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_api,
                meta={"page": next_page},
                headers={"Accept": "application/json"},
            )
