"""
Spider for scraping Yahoo Shopping (Japan) - https://shopping.yahoo.co.jp/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Use Playwright to render category listing pages
2. Extract product data directly from product cards on listing pages
3. Follow pagination to get more products

Note: Yahoo Shopping has anti-bot protection on product pages, so we extract
data directly from listing pages where product cards show name, price, and URL.
"""

import scrapy
import logging
import re
from datetime import datetime
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


def _abort_heavy_requests(request) -> bool:
    """Best-effort: skip heavy assets to reduce timeouts."""
    resource_type = getattr(request, "resource_type", None)
    if resource_type in {"image", "media", "font", "stylesheet"}:
        return True

    url = getattr(request, "url", "") or ""
    return any(
        url.endswith(ext)
        for ext in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".otf",
            ".css",
        )
    )


class YahooShoppingSpider(scrapy.Spider):
    """
    Spider for Yahoo Shopping (Japan).
    Extracts product data from category listing pages using Playwright.
    """

    name = "yahoo_shopping"
    allowed_domains = ["shopping.yahoo.co.jp"]
    country = "japan"
    currency = "JPY"
    language = "jp"

    # Category IDs to scrape (covers all major product categories)
    CATEGORY_IDS = [
        # Food & Health
        ("2498", "食品"),
        ("2500", "ダイエット、健康"),
        ("2501", "コスメ、美容、ヘアケア"),
        # Fashion
        ("2494", "レディースファッション"),
        ("2495", "メンズファッション"),
        ("2496", "腕時計、アクセサリー"),
        # Kids & Baby
        ("2497", "ベビー、キッズ、マタニティ"),
        # Electronics
        ("2502", "スマートフォン、タブレット、パソコン"),
        ("2504", "テレビ、オーディオ、カメラ"),
        ("2505", "家電"),
        # Home & Living
        ("2506", "家具、インテリア"),
        ("2508", "キッチン、日用品、文具"),
        # Sports & Outdoor
        ("2512", "スポーツ"),
        ("2513", "アウトドア、釣り、旅行用品"),
    ]

    # Maximum pages per category
    MAX_PAGES_PER_CATEGORY = 3

    # Custom settings for Playwright
    custom_settings = {
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 120000,
        "PLAYWRIGHT_ABORT_REQUEST": _abort_heavy_requests,
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def start_requests(self):
        """
        Start by requesting category listing pages using Playwright.
        """
        for category_id, category_name in self.CATEGORY_IDS:
            # Use the recommend page which shows product listings
            url = f"https://shopping.yahoo.co.jp/category/{category_id}/recommend"
            yield scrapy.Request(
                url,
                callback=self.parse_category_listing,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": 1,
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_goto_kwargs": {
                        # networkidle tends to hang on Yahoo pages due to long-lived requests.
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                    ],
                },
                errback=self.errback_httpbin,
            )

    def parse_category_listing(self, response):
        """
        Parse category listing page and extract product data from product cards.
        """
        category_id = response.meta.get("category_id")
        category_name = response.meta.get("category_name")
        page = response.meta.get("page", 1)

        # Check response length
        response_len = len(response.text)
        logger.info(f"Response length for {category_name}: {response_len} chars")

        if response_len < 1000:
            logger.warning(
                f"Short response for category {category_name}: {response_len} chars"
            )
            return

        # Extract product cards from the listing page
        # Yahoo Shopping uses 'item' class for product cards
        product_cards = response.css(
            "div.item, li.item, div[class*='item '], div.items > div"
        )

        items_found = 0
        for card in product_cards:
            item = self._parse_product_card(card, category_name)
            if item:
                items_found += 1
                yield item

        logger.info(f"Found {items_found} products in {category_name} (page {page})")

        # Follow pagination if we found items and haven't reached max pages
        if items_found > 0 and page < self.MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            next_url = f"https://shopping.yahoo.co.jp/category/{category_id}/recommend?page={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_category_listing,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": next_page,
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                    ],
                },
                errback=self.errback_httpbin,
            )

    def _parse_product_card(self, card, category_name):
        """
        Extract product data from a product card element.
        Yahoo Shopping uses item-* classes for product data.
        """
        # Try multiple selectors for product name
        product_name = (
            card.css("a.item-link::attr(title)").get()
            or card.css("img::attr(alt)").get()
            or card.css("a[class*='name']::text").get()
            or card.css("div[class*='title']::text").get()
            or card.css("span[class*='name']::text").get()
        )

        # Try multiple selectors for price - Yahoo uses item-price-value
        price_text = (
            card.css("span.item-price-value::text").get()
            or card.css("div.item-price-value::text").get()
            or card.css("span[class*='price-value']::text").get()
            or card.css("div.item-price::text").get()
            or card.css("span[class*='price']::text").get()
        )

        # Try to get product URL
        product_url = (
            card.css("a.item-link::attr(href)").get()
            or card.css("a[href*='store.shopping.yahoo.co.jp']::attr(href)").get()
            or card.css("a[href*='shopping.yahoo.co.jp']::attr(href)").get()
            or card.css("a::attr(href)").get()
        )

        if not product_name or not price_text:
            return None

        # Clean the price
        price = self._clean_price(price_text)
        if not price:
            return None

        # Extract product ID from URL
        product_id = (
            self._extract_product_id_from_url(product_url) if product_url else None
        )

        # Skip duplicates
        if product_id and product_id in self.scraped_product_ids:
            return None
        if product_id:
            self.scraped_product_ids.add(product_id)

        return {
            "product_name": product_name.strip(),
            "category": category_name,
            "price": price,
            "currency": self.currency,
            "url": product_url or "",
            "product_id": product_id,
            "language": self.language,
            "scraped_at_utc": datetime.utcnow().isoformat(),
        }

    def _clean_price(self, price_str):
        """
        Clean price string - remove currency symbols, commas, and extract number.
        """
        if not price_str:
            return None
        # Remove yen symbol, commas, spaces, and '円'
        cleaned = re.sub(r"[¥￥,\s円]", "", str(price_str))
        # Extract first number
        match = re.search(r"(\d+)", cleaned)
        if match:
            return match.group(1)
        return cleaned

    def _extract_product_id_from_url(self, url):
        """
        Extract product ID from Yahoo Shopping URL.
        URL format: https://store.shopping.yahoo.co.jp/{store_id}/{item_id}.html
        """
        # Try store.shopping.yahoo.co.jp pattern
        match = re.search(r"store\.shopping\.yahoo\.co\.jp/([^/]+)/([^/]+)", url)
        if match:
            return f"{match.group(1)}_{match.group(2).replace('.html', '')}"

        # Try paypaymall pattern
        match = re.search(r"paypaymall\.yahoo\.co\.jp/store/([^/]+)/item/([^/]+)", url)
        if match:
            return f"{match.group(1)}_{match.group(2)}"

        return None

    def errback_httpbin(self, failure):
        """
        Handle request failures.
        """
        logger.error(f"Request failed: {failure.request.url}")
