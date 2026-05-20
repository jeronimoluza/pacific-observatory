"""
Spider for scraping FairPrice (Singapore) - https://www.fairprice.com.sg/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Use Playwright with stealth settings to render JavaScript-heavy pages
2. Extract product data from category listing pages
3. Follow pagination to get more products
"""

import scrapy
import logging
import re
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class FairPriceSpider(scrapy.Spider):
    """
    Spider for FairPrice (Singapore).
    Uses Playwright to render pages and extract product data from listings.
    """

    name = "fairprice"
    allowed_domains = ["www.fairprice.com.sg"]
    currency = "SGD"

    # Category URLs to scrape
    CATEGORIES = [
        (
            "https://www.fairprice.com.sg/category/fruits-vegetables",
            "Fruits & Vegetables",
        ),
        ("https://www.fairprice.com.sg/category/meat-seafood", "Meat & Seafood"),
        (
            "https://www.fairprice.com.sg/category/dairy-chilled-eggs",
            "Dairy, Chilled & Eggs",
        ),
        (
            "https://www.fairprice.com.sg/category/rice-noodles-cooking-ingredients",
            "Rice, Noodles & Cooking",
        ),
        ("https://www.fairprice.com.sg/category/beverages", "Beverages"),
        (
            "https://www.fairprice.com.sg/category/snacks-confectionery",
            "Snacks & Confectionery",
        ),
        ("https://www.fairprice.com.sg/category/health-beauty", "Health & Beauty"),
        ("https://www.fairprice.com.sg/category/household", "Household"),
        ("https://www.fairprice.com.sg/category/baby", "Baby"),
        (
            "https://www.fairprice.com.sg/category/breakfast-spreads-canned-food",
            "Breakfast & Canned Food",
        ),
    ]

    MAX_PAGES_PER_CATEGORY = 5

    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 1,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def start_requests(self):
        for url, category_name in self.CATEGORIES:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "category_name": category_name,
                    "page": 1,
                    "base_url": url,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                errback=self.errback_handler,
            )

    async def parse_listing(self, response):
        """Parse category listing page and extract product data from cards."""
        category_name = response.meta.get("category_name")
        page = response.meta.get("page", 1)
        base_url = response.meta.get("base_url")
        playwright_page = response.meta.get("playwright_page")

        if playwright_page:
            await playwright_page.close()

        response_len = len(response.text)
        logger.info(
            f"Response length for {category_name} (page {page}): {response_len} chars"
        )

        if response_len < 1000:
            logger.warning(f"Short response for {category_name}: {response_len} chars")
            return

        # Extract product cards
        product_cards = response.css(
            "div.product-container, " "div[data-testid='product'], " "div.product-card"
        )

        items_found = 0
        for card in product_cards:
            item = self._parse_product_card(card, category_name, response)
            if item:
                items_found += 1
                yield item

        logger.info(f"Found {items_found} products in {category_name} (page {page})")

        # Pagination
        if items_found > 0 and page < self.MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            next_url = f"{base_url}?page={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_listing,
                meta={
                    "category_name": category_name,
                    "page": next_page,
                    "base_url": base_url,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                errback=self.errback_handler,
            )

    def _parse_product_card(self, card, category_name, response):
        """Extract product data from a product card element."""
        product_name = (
            card.css("img[alt]::attr(alt)").get()
            or card.css("a::attr(title)").get()
            or card.css("span[class*='name']::text").get()
            or card.css("div[class*='title']::text").get()
        )

        # Extract price from all text content using dollar pattern
        all_text = " ".join(card.css("*::text").getall())
        price_text = None
        price_match = re.search(r"\$\s*([\d.]+)", all_text)
        if price_match:
            price_text = price_match.group(1)

        if not price_text:
            price_text = (
                card.css("span[class*='price']::text").get()
                or card.css("div[class*='price']::text").get()
            )

        product_url = (
            card.css("a[href*='/product/']::attr(href)").get()
            or card.css("a::attr(href)").get()
        )

        if not product_name or not price_text:
            return None

        price = self._clean_price(price_text)
        if not price:
            return None

        # Deduplication by URL
        if product_url and product_url in self.scraped_product_ids:
            return None
        if product_url:
            self.scraped_product_ids.add(product_url)

        return {
            "product_name": product_name.strip(),
            "category": category_name,
            "price": price,
            "currency": self.currency,
            "url": response.urljoin(product_url) if product_url else response.url,
            "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
        }

    def _clean_price(self, price_str):
        """Clean SGD price string (e.g., '$3.50' -> '3.50')."""
        if not price_str:
            return None
        cleaned = re.sub(r"[$\s]", "", str(price_str))
        match = re.search(r"(\d+\.?\d*)", cleaned)
        return match.group(1) if match else None

    def errback_handler(self, failure):
        logger.error(f"Request failed: {failure.request.url}")
