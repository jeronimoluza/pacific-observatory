"""
Spider for scraping Thai Huot (Cambodia) - https://www.thaihuot.com/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Start from category pages to discover all products
2. Follow product detail links to extract full product data
3. Extract: product_name, price (USD), category, product_id (SKU)
"""

import scrapy
from urllib.parse import urljoin
import logging
import re

from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class ThaiHuotSpider(scrapy.Spider):
    """
    Spider for Thai Huot (Cambodia).
    Discovers product pages from category listings and extracts price data.
    """

    name = "thai_huot"
    allowed_domains = ["thaihuot.com", "www.thaihuot.com"]
    country = "cambodia"
    currency = "USD"

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("thai_huot")

    # All known category slugs from the website
    CATEGORIES = [
        "butter-cheese",
        "canned-food",
        "womens-fashion",  # Cereals
        "dairy",  # Delicatessen
        "Drinks",
        "frozen-fruit",  # Frozen
        "ice-cream",
        "liqeuer",
        "milk",
        "cooking-oil",  # Oil
        "pasta-sauce",
        "snack",
        "kids",  # Tea
        "yogurt-and-drink",
    ]

    def start_requests(self):
        """
        Generate initial requests for all category pages.
        """
        for category in self.CATEGORIES:
            url = f"https://www.thaihuot.com/product-cat/{category}"
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                meta={"category": category},
            )

    def parse_category(self, response):
        """
        Parse category page and extract product data directly from listing.
        Product detail pages return errors, so we extract from the listing page.
        """
        category = response.meta.get("category", "unknown")
        scraped_at = response.headers.get("Date", b"").decode("utf-8")

        # Extract all product data from page-level selectors
        # The HTML structure has product info spread across sibling divs
        names = response.css("h3.title a::text").getall()
        prices = response.css("div.product-price span::text").getall()
        urls = response.css("h3.title a::attr(href)").getall()

        logger.info(f"Found {len(names)} products in category '{category}'")

        # Zip the data together
        for i, (product_name, price) in enumerate(zip(names, prices)):
            product_url = urls[i] if i < len(urls) else None

            if product_url:
                product_url = urljoin(response.url, product_url)

            # Skip if no name or price
            if not product_name or not price:
                continue

            # Clean HTML entities from product name
            product_name = product_name.replace("&quot;", '"').replace("&amp;", "&")

            # Extract product_id (SKU) from product name
            # Format: "PRODUCT NAME (SKU123)"
            product_id = None
            sku_match = re.search(r"\(([^)]+)\)\s*$", product_name)
            if sku_match:
                product_id = sku_match.group(1)

            # Clean product name by removing SKU if present
            clean_name = re.sub(r"\s*\([^)]+\)\s*$", "", product_name).strip()

            yield {
                "product_id": product_id,
                "product_name": clean_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": product_url,
                "scraped_at": scraped_at,
            }
            logger.debug(f"Scraped product: {clean_name} - {price} {self.currency}")
