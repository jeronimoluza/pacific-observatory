"""
Spider for scraping Makro (Cambodia) - https://www.makrocambodiaclick.com/en
Extracts product information including prices, categories, and URLs.

Strategy:
1. Start from homepage, discover all main categories
2. Recursively follow subcategory links until reaching leaf categories (no more subcategories)
3. From leaf categories, scrape all product links (using Playwright for JS rendering)
4. Extract product data with category path like "Butchery - Beef"

Note: This spider uses scrapy-playwright for JavaScript rendering since the
Makro website loads products dynamically via JavaScript.
"""

import scrapy
import logging
import re
from urllib.parse import urljoin
from scrapy_playwright.page import PageMethod

from price_scraping.utils import SelectorExtractor
from price_scraping.selectors import get_selectors

logger = logging.getLogger(__name__)


class MakroSpider(scrapy.Spider):
    """
    Spider for Makro (Cambodia).
    Recursively discovers deepest categories and scrapes products from them.
    """

    name = "makro"
    allowed_domains = ["makrocambodiaclick.com"]
    start_urls = ["https://www.makrocambodiaclick.com/en/"]
    country = "cambodia"
    currency = "KHR"
    active = False  # Spider is currently not working

    # CSS selector fallbacks for product fields
    SELECTORS = get_selectors("makro")

    # Main categories to scrape (from homepage)
    MAIN_CATEGORIES = [
        "Bakery",
        "Butchery",
        "Chilled&DairyProducts",
        "Fish&Seafood",
        "Frozenfood",
        "Fruits&Vegetables",
        "Beverages",
        "DryGroceries",
        "PersonalCareProducts",
        "Snacks",
        "CleaningProducts",
        "ElectricAppliances",
        "Households",
        "OfficeSuppliesAndStationaries",
        "PetsFood&PetsCare",
    ]

    # Patterns to identify subcategory and product links
    CATEGORY_PATTERN = re.compile(r"/en/category/(.+)")
    PRODUCT_PATTERN = re.compile(r"/en/products/(\d+)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def start_requests(self):
        """
        Start by requesting all main category pages with Playwright rendering.
        """
        for category in self.MAIN_CATEGORIES:
            url = f"https://www.makrocambodiaclick.com/en/category/{category}"
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                meta={
                    "category_path": [self._format_category_name(category)],
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "networkidle",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
            )

    def _format_category_name(self, category_slug):
        """
        Format category slug to readable name.
        E.g., 'Chilled&DairyProducts' -> 'Chilled & Dairy Products'
        """
        # Add spaces before capital letters and around &
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", category_slug)
        name = name.replace("&", " & ")
        # Clean up multiple spaces
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def parse_category(self, response):
        """
        Parse a category page.
        - If subcategories exist, follow them recursively
        - If no subcategories (leaf category), scrape products
        """
        category_path = response.meta.get("category_path", [])
        current_url = response.url

        # Find subcategory links - they appear in the "Sub Category" section
        # Look for links that extend the current category path
        subcategory_links = []

        # Extract all category links from the page
        all_links = response.css("a[href*='/en/category/']::attr(href)").getall()

        # Filter to find subcategories of current category
        current_category_match = self.CATEGORY_PATTERN.search(current_url)
        if current_category_match:
            current_category_path = current_category_match.group(1)

            for link in all_links:
                full_url = urljoin(response.url, link)
                match = self.CATEGORY_PATTERN.search(full_url)
                if match:
                    link_path = match.group(1)
                    # Check if this is a direct subcategory (extends current path)
                    if (
                        link_path.startswith(current_category_path + "/")
                        and link_path.count("/") == current_category_path.count("/") + 1
                    ):
                        subcategory_links.append(full_url)

        # Remove duplicates
        subcategory_links = list(set(subcategory_links))

        if subcategory_links:
            # Has subcategories - follow them
            logger.info(
                f"Category '{' - '.join(category_path)}' has {len(subcategory_links)} subcategories"
            )
            for subcat_url in subcategory_links:
                # Extract subcategory name from URL
                match = self.CATEGORY_PATTERN.search(subcat_url)
                if match:
                    subcat_path = match.group(1)
                    subcat_name = subcat_path.split("/")[-1]
                    new_path = category_path + [self._format_category_name(subcat_name)]

                    yield scrapy.Request(
                        subcat_url,
                        callback=self.parse_category,
                        meta={
                            "category_path": new_path,
                            "playwright": True,
                            "playwright_include_page": False,
                            "playwright_page_goto_kwargs": {
                                "wait_until": "networkidle",
                            },
                            "playwright_page_methods": [
                                PageMethod("wait_for_timeout", 2000),
                            ],
                        },
                    )
        else:
            # Leaf category - scrape products
            logger.info(
                f"Leaf category found: '{' - '.join(category_path)}' - scraping products"
            )
            yield from self.scrape_products_from_category(response, category_path)

    def scrape_products_from_category(self, response, category_path):
        """
        Extract product links from a leaf category page and scrape them.
        """
        # Find all product links
        product_links = response.css("a[href*='/en/products/']::attr(href)").getall()
        product_links = list(set(product_links))  # Remove duplicates

        logger.info(
            f"Found {len(product_links)} products in '{' - '.join(category_path)}'"
        )

        for link in product_links:
            full_url = urljoin(response.url, link)
            match = self.PRODUCT_PATTERN.search(full_url)
            if match:
                product_id = match.group(1)
                if product_id not in self.scraped_product_ids:
                    self.scraped_product_ids.add(product_id)
                    yield scrapy.Request(
                        full_url,
                        callback=self.parse_product,
                        meta={
                            "category_path": category_path,
                            "product_id": product_id,
                            "playwright": True,
                            "playwright_include_page": False,
                            "playwright_page_goto_kwargs": {
                                "wait_until": "networkidle",
                            },
                            "playwright_page_methods": [
                                PageMethod("wait_for_timeout", 2000),
                            ],
                        },
                    )

    def parse_product(self, response):
        """
        Parse product page and extract relevant data.
        Category is passed from the category page via meta.
        """
        category_path = response.meta.get("category_path", [])
        product_id = response.meta.get("product_id")

        # Initialize extractor with fallback selectors
        extractor = SelectorExtractor(response, logger)

        # Extract product information using fallback selectors
        product_name = extractor.extract(
            "product_name", self.SELECTORS.get("product_name", [])
        )
        price = extractor.extract("price", self.SELECTORS.get("price", []))
        details = extractor.extract("details", self.SELECTORS.get("details", []))

        # Format category as "Parent - Child" format
        category = " - ".join(category_path) if category_path else None

        if product_name and price:
            yield {
                "product_name": product_name,
                "category": category,
                "price": price,
                "details": details,
                "currency": self.currency,
                "url": response.url,
                "product_id": product_id,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            logger.info(f"Scraped product: {product_name} (category: {category})")
        else:
            logger.warning(
                f"Could not extract product data from {response.url} "
                f"(name: {product_name}, price: {price})"
            )
