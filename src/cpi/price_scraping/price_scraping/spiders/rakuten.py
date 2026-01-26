"""
Spider for scraping Rakuten (Japan) - https://www.rakuten.co.jp/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Use Playwright with stealth settings to render JavaScript-heavy pages
2. Extract product data from category listing pages
3. Follow pagination to get more products

Note: Rakuten has strong anti-bot protection, so we use Playwright
with proper browser emulation to bypass detection.
"""

import scrapy
import logging
import re
import json
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class RakutenSpider(scrapy.Spider):
    """
    Spider for Rakuten (Japan).
    Uses Playwright to render pages and extract product data from listings.
    """

    name = "rakuten"
    allowed_domains = ["rakuten.co.jp", "search.rakuten.co.jp"]
    country = "japan"
    currency = "JPY"
    language = "jp"

    # Category IDs to scrape (numeric IDs from Rakuten's category system)
    CATEGORY_IDS = [
        # Food categories
        ("100227", "食品"),
        ("201184", "米・白米"),
        ("100269", "和風惣菜"),
        ("100275", "洋風惣菜"),
        ("110428", "牛肉"),
        ("200929", "豚肉"),
        ("200939", "鶏肉"),
        ("110411", "カニ"),
        ("207770", "マグロ"),
        # Fashion
        ("555086", "レディーストップス"),
        ("555089", "レディースボトムス"),
        ("110765", "メンズトップス"),
        ("558846", "メンズパンツ"),
        # Electronics
        ("564497", "ノートPC"),
        ("100026", "デスクトップPC"),
        ("211742", "スマートフォン本体"),
        # Home & Kitchen
        ("558944", "食器"),
        ("215783", "調理器具"),
        # Beauty
        ("100939", "スキンケア"),
        ("100945", "メイクアップ"),
        # Sports
        ("101070", "ランニング"),
        ("101077", "フィットネス"),
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
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scraped_product_ids = set()

    def start_requests(self):
        """
        Start by requesting search results for each category using Playwright.
        """
        for category_id, category_name in self.CATEGORY_IDS:
            # Use search.rakuten.co.jp which has product listings
            url = f"https://search.rakuten.co.jp/search/mall/-/{category_id}/"
            yield scrapy.Request(
                url,
                callback=self.parse_search_results,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": 1,
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "networkidle",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 3000),
                    ],
                },
                errback=self.errback_httpbin,
            )

    def parse_search_results(self, response):
        """
        Parse search results page and extract product data.
        Rakuten search pages have product cards with name, price, and URL.
        """
        category_id = response.meta.get("category_id")
        category_name = response.meta.get("category_name")
        page = response.meta.get("page", 1)

        # Check if we got a valid response
        response_len = len(response.text)
        logger.info(f"Response length for {category_name}: {response_len} chars")

        if response_len < 1000:
            logger.warning(
                f"Short response for category {category_name}: {response_len} chars"
            )
            # Log first 200 chars to see what we got
            logger.debug(f"Response content: {response.text[:200]}")
            return

        # Try to find embedded JSON data in the page
        # Rakuten often embeds product data in script tags
        scripts = response.css("script::text").getall()
        for script in scripts:
            if "itemList" in script or "searchResult" in script or '"items"' in script:
                try:
                    # Try to extract JSON from script
                    json_match = re.search(r'(\{[^{}]*"items?"[^{}]*\})', script)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        items = data.get("items", data.get("itemList", []))
                        for item in items:
                            yield from self._parse_json_item(item, category_name)
                except (json.JSONDecodeError, AttributeError):
                    pass

        # Extract product cards from HTML using multiple selector strategies
        # Rakuten uses various class names for product cards
        product_cards = response.css(
            "div.searchresultitem, "
            "div[class*='dui-card'], "
            "div[class*='item-box'], "
            "li[class*='searchresultitem'], "
            "div[data-ratid], "
            "div.content--item"
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
            next_url = f"https://search.rakuten.co.jp/search/mall/-/{category_id}/?p={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_search_results,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": next_page,
                    "playwright": True,
                    "playwright_include_page": False,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "networkidle",
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
        """
        # Try multiple selectors for product name
        product_name = (
            card.css("h2 a::text").get()
            or card.css("a.title::text").get()
            or card.css("div[class*='title'] a::text").get()
            or card.css("a[class*='item-name']::text").get()
            or card.css("span[class*='item-name']::text").get()
        )

        # Try multiple selectors for price
        price_text = (
            card.css("span[class*='price']::text").get()
            or card.css("div[class*='price']::text").get()
            or card.css("span.important::text").get()
        )

        # Try to get product URL
        product_url = (
            card.css("a[href*='item.rakuten.co.jp']::attr(href)").get()
            or card.css("h2 a::attr(href)").get()
            or card.css("a.title::attr(href)").get()
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
        }

    def _parse_json_item(self, item, category_name):
        """
        Parse a product item from JSON data.
        """
        product_name = item.get("itemName") or item.get("name") or item.get("title")
        price = item.get("itemPrice") or item.get("price")
        product_url = item.get("itemUrl") or item.get("url")
        product_id = item.get("itemCode") or item.get("id")

        if not product_name or not price:
            return

        # Skip duplicates
        if product_id and product_id in self.scraped_product_ids:
            return
        if product_id:
            self.scraped_product_ids.add(product_id)

        yield {
            "product_name": str(product_name).strip(),
            "category": category_name,
            "price": str(price),
            "currency": self.currency,
            "url": product_url or "",
            "product_id": product_id,
            "language": self.language,
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
        return None

    def _extract_product_id_from_url(self, url):
        """
        Extract product ID from Rakuten URL.
        URL format: https://item.rakuten.co.jp/{shop_id}/{item_id}/
        For redirect URLs, extract the 'ii' parameter which is the item identifier.
        """
        if not url:
            return None
        # Try direct product URL format
        match = re.search(r"item\.rakuten\.co\.jp/([^/]+)/([^/?]+)", url)
        if match:
            return f"{match.group(1)}_{match.group(2)}"
        # Try redirect URL format - extract 'ii' parameter
        match = re.search(r"[?&]ii=([^&]+)", url)
        if match:
            return match.group(1)
        return None

    def errback_httpbin(self, failure):
        """
        Handle request failures.
        """
        logger.error(f"Request failed: {failure.request.url}")
