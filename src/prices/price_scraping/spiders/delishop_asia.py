"""
Spider for scraping Delishop Asia (Cambodia) - https://delishop.asia/
Extracts product information from the JSON API.
Scrapes: product_name, category, price (KHR), and weight.
"""

import scrapy
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DelishopAsiaSpider(scrapy.Spider):
    """
    Spider for Delishop Asia (Cambodia).
    Uses the JSON API to extract product data from all categories.
    """

    name = "delishop_asia"
    allowed_domains = ["api.delishop.asia", "delishop.asia"]
    currency = "USD"

    # API configuration
    API_BASE = "https://api.delishop.asia/api/products"
    ITEMS_PER_PAGE = 25
    STORE_ID = 1

    # All category slugs from the website
    CATEGORIES = [
        "meat-poultry",
        "vegetables-fruits",
        "dairy-products",
        "seafood",
        "ready-meal-caterer",
        "breakfast",
        "baking",
        "sweet-corner",
        "babys-world",
        "pantry",
        "water",
        "soda",
        "fruit-drinks",
        "milk",
        "coffee-tea",
        "wine",
        "spirit",
        "beer-cider",
        "personal-care",
        "baby-care",
        "pharmacy-parapharmacy",
        "cosmetics-make-up",
        "jewelry",
        "nutrition-product",
        "household-essentials",
        "games-toys",
        "electronic-computer",
        "pets",
        "homewares-accessories",
        "stationery",
        "tableware",
    ]

    async def start(self):
        """
        Generate initial requests for page 1 of each category.
        """
        for category in self.CATEGORIES:
            url = self._build_api_url(category, page=1)
            yield scrapy.Request(
                url,
                callback=self.parse_api_response,
                meta={"category_slug": category, "page": 1},
                headers={"Accept": "application/json"},
            )

    def _build_api_url(self, category: str, page: int) -> str:
        """Build the API URL for a given category and page."""
        return (
            f"{self.API_BASE}?page={page}&limit={self.ITEMS_PER_PAGE}"
            f"&category={category}&store_id={self.STORE_ID}"
            f"&append=true&pagetype=web&_locale=en"
        )

    def parse_api_response(self, response):
        """
        Parse the JSON API response and extract product data.
        Handles pagination by requesting next page if more products exist.
        """
        category_slug = response.meta["category_slug"]
        current_page = response.meta["page"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from {response.url}")
            return

        if not data.get("success") or data.get("error"):
            logger.warning(
                f"API returned error for {category_slug} page {current_page}"
            )
            return

        products = data.get("data", [])

        if not products:
            logger.info(
                f"No more products for category '{category_slug}' at page {current_page}"
            )
            return

        logger.info(
            f"Processing {len(products)} products from '{category_slug}' page {current_page}"
        )

        scraped_at = datetime.utcnow().isoformat()

        for product in products:
            # Extract category name from nested object
            category_name = None
            if product.get("category") and isinstance(product["category"], dict):
                category_name = product["category"].get("name")

            # Combine name + weight for product_name
            name = product.get("name") or product.get("nameLocal") or ""
            weight = product.get("weight") or ""
            product_name = f"{name} {weight}".strip() if weight else name

            # Extract product data
            item = {
                "product_name": product_name,
                "category": category_name,
                "price": product.get("price"),
                "currency": self.currency,
                "product_id": product.get("id"),
                "barcode": product.get("barCode"),
                "url": f"https://delishop.asia/product/{product.get('refId')}",
                "scraped_at": scraped_at,
            }

            # Only yield if we have essential fields
            if item["product_name"] and item["price"] is not None:
                yield item
                logger.debug(
                    f"Scraped: {item['product_name']} - {item['price']} {self.currency}"
                )
            else:
                logger.warning(f"Missing data for product ID {product.get('id')}")

        # Request next page if we got a full page of results
        if len(products) >= self.ITEMS_PER_PAGE:
            next_page = current_page + 1
            next_url = self._build_api_url(category_slug, next_page)
            yield scrapy.Request(
                next_url,
                callback=self.parse_api_response,
                meta={"category_slug": category_slug, "page": next_page},
                headers={"Accept": "application/json"},
            )
