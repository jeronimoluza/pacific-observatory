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
from datetime import datetime
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
    MAX_PAGES_PER_CATEGORY = 5

    # Products per page on Rakuten search
    PRODUCTS_PER_PAGE = 45

    # Custom settings for Playwright
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
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 1,  # Lower to avoid rate limiting
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
            # Add sorting by standard (default) to get consistent results
            url = f"https://search.rakuten.co.jp/search/mall/-/{category_id}/?s=1&p=1"
            yield scrapy.Request(
                url,
                callback=self.parse_search_results,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": 1,
                    "playwright": True,
                    "playwright_include_page": True,  # Need page object for scrolling
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        # Wait for the search results container to load
                        PageMethod(
                            "wait_for_selector",
                            "div.searchresultitems, div[class*='dui-container']",
                            timeout=30000,
                        ),
                        # Scroll down to trigger lazy loading
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate", "window.scrollTo(0, document.body.scrollHeight)"
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                errback=self.errback_httpbin,
            )

    async def parse_search_results(self, response):
        """
        Parse search results page and extract product data.
        Rakuten search pages have product cards with name, price, and URL.
        """
        category_id = response.meta.get("category_id")
        category_name = response.meta.get("category_name")
        page = response.meta.get("page", 1)
        playwright_page = response.meta.get("playwright_page")

        # Close the page if we have it (to free resources)
        if playwright_page:
            await playwright_page.close()

        # Check if we got a valid response
        response_len = len(response.text)
        logger.info(
            f"Response length for {category_name} (page {page}): {response_len} chars"
        )

        if response_len < 5000:
            logger.warning(
                f"Short response for category {category_name}: {response_len} chars"
            )
            return

        # Primary strategy: Extract from the main search results grid
        # Rakuten's search results use specific data attributes and class patterns
        items_found = 0

        # Strategy 1: Look for product cards with data-ratid (Rakuten tracking ID)
        product_cards = response.css("div[data-ratid]")
        logger.info(f"Found {len(product_cards)} cards with data-ratid")

        for card in product_cards:
            item = self._parse_product_card_v2(card, category_name)
            if item:
                items_found += 1
                yield item

        # Strategy 2: Look for searchresultitem class (older layout)
        if items_found == 0:
            product_cards = response.css("div.searchresultitem")
            logger.info(f"Found {len(product_cards)} searchresultitem cards")
            for card in product_cards:
                item = self._parse_product_card(card, category_name)
                if item:
                    items_found += 1
                    yield item

        # Strategy 3: Look for dui-card elements (newer design system)
        if items_found == 0:
            product_cards = response.css("div[class*='dui-card']")
            logger.info(f"Found {len(product_cards)} dui-card elements")
            for card in product_cards:
                item = self._parse_dui_card(card, category_name)
                if item:
                    items_found += 1
                    yield item

        # Strategy 4: Extract from embedded JSON in script tags
        if items_found == 0:
            scripts = response.css("script::text").getall()
            for script in scripts:
                if '"Items"' in script or '"itemList"' in script:
                    try:
                        # Look for the search results JSON structure
                        json_match = re.search(r'"Items"\s*:\s*(\[[^\]]+\])', script)
                        if json_match:
                            items_data = json.loads(json_match.group(1))
                            for item_wrapper in items_data:
                                item_data = item_wrapper.get("Item", item_wrapper)
                                parsed = self._parse_json_item_v2(
                                    item_data, category_name
                                )
                                if parsed:
                                    items_found += 1
                                    yield parsed
                    except (json.JSONDecodeError, AttributeError) as e:
                        logger.debug(f"JSON parse error: {e}")

        logger.info(
            f"Total: Found {items_found} products in {category_name} (page {page})"
        )

        # Follow pagination if we found items and haven't reached max pages
        if items_found > 0 and page < self.MAX_PAGES_PER_CATEGORY:
            next_page = page + 1
            next_url = f"https://search.rakuten.co.jp/search/mall/-/{category_id}/?s=1&p={next_page}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_search_results,
                meta={
                    "category_id": category_id,
                    "category_name": category_name,
                    "page": next_page,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod(
                            "wait_for_selector",
                            "div.searchresultitems, div[class*='dui-container']",
                            timeout=30000,
                        ),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate", "window.scrollTo(0, document.body.scrollHeight)"
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                errback=self.errback_httpbin,
            )

    def _parse_product_card(self, card, category_name):
        """
        Extract product data from a product card element (legacy selectors).
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

        # Try to get product URL - prefer direct item URLs, skip ad redirects
        product_url = card.css("a[href*='item.rakuten.co.jp']::attr(href)").get()
        if not product_url:
            # Get any link but filter out ad redirects later
            product_url = (
                card.css("h2 a::attr(href)").get()
                or card.css("a.title::attr(href)").get()
            )

        # Skip sponsored/ad products (redirect URLs)
        if product_url and "ias.rakuten.co.jp/redirect" in product_url:
            return None

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

    def _parse_product_card_v2(self, card, category_name):
        """
        Extract product data from cards with data-ratid attribute.
        These are the main search result items.
        """
        # Get the product link - should be a direct item.rakuten.co.jp link
        product_url = card.css("a[href*='item.rakuten.co.jp']::attr(href)").get()

        # Skip if no direct product URL or if it's an ad redirect
        if not product_url:
            return None
        if "ias.rakuten.co.jp/redirect" in product_url:
            return None

        # Product name from the link title or text
        product_name = (
            card.css("a[href*='item.rakuten.co.jp']::attr(title)").get()
            or card.css("a[href*='item.rakuten.co.jp']::text").get()
            or card.css("h2::text").get()
            or card.css("h3::text").get()
            or card.css("div[class*='title']::text").get()
            or card.css("span[class*='content']::text").get()
        )

        # If still no name, try getting all text from the card
        if not product_name:
            all_text = card.css("a[href*='item.rakuten.co.jp'] *::text").getall()
            if all_text:
                product_name = " ".join([t.strip() for t in all_text if t.strip()])

        # Price - look for yen amounts
        price_text = (
            card.css("span[class*='price']::text").get()
            or card.css("div[class*='price']::text").get()
            or card.css("span.important::text").get()
        )

        # If no price found, search all text for yen pattern
        if not price_text:
            all_text = " ".join(card.css("*::text").getall())
            price_match = re.search(r"([\d,]+)円", all_text)
            if price_match:
                price_text = price_match.group(1)

        if not product_name or not price_text:
            return None

        # Clean the price
        price = self._clean_price(price_text)
        if not price:
            return None

        # Extract product ID from URL
        product_id = self._extract_product_id_from_url(product_url)

        # Skip duplicates
        if product_id and product_id in self.scraped_product_ids:
            return None
        if product_id:
            self.scraped_product_ids.add(product_id)

        return {
            "product_name": product_name.strip()[:500],  # Limit length
            "category": category_name,
            "price": price,
            "currency": self.currency,
            "url": product_url,
            "product_id": product_id,
            "language": self.language,
            "scraped_at_utc": datetime.utcnow().isoformat(),
        }

    def _parse_dui_card(self, card, category_name):
        """
        Extract product data from Rakuten's newer dui-card design system.
        """
        # Get the product link
        product_url = card.css("a[href*='item.rakuten.co.jp']::attr(href)").get()

        if not product_url:
            return None
        if "ias.rakuten.co.jp/redirect" in product_url:
            return None

        # Product name
        product_name = (
            card.css("a::attr(title)").get()
            or card.css("img::attr(alt)").get()
            or card.css("[class*='title']::text").get()
        )

        # Price
        price_text = card.css("[class*='price']::text").get()
        if not price_text:
            all_text = " ".join(card.css("*::text").getall())
            price_match = re.search(r"([\d,]+)円", all_text)
            if price_match:
                price_text = price_match.group(1)

        if not product_name or not price_text:
            return None

        price = self._clean_price(price_text)
        if not price:
            return None

        product_id = self._extract_product_id_from_url(product_url)

        if product_id and product_id in self.scraped_product_ids:
            return None
        if product_id:
            self.scraped_product_ids.add(product_id)

        return {
            "product_name": product_name.strip()[:500],
            "category": category_name,
            "price": price,
            "currency": self.currency,
            "url": product_url,
            "product_id": product_id,
            "language": self.language,
            "scraped_at_utc": datetime.utcnow().isoformat(),
        }

    def _parse_json_item(self, item, category_name):
        """
        Parse a product item from JSON data (legacy format).
        """
        product_name = item.get("itemName") or item.get("name") or item.get("title")
        price = item.get("itemPrice") or item.get("price")
        product_url = item.get("itemUrl") or item.get("url")
        product_id = item.get("itemCode") or item.get("id")

        if not product_name or not price:
            return

        # Skip ad redirects
        if product_url and "ias.rakuten.co.jp/redirect" in product_url:
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

    def _parse_json_item_v2(self, item, category_name):
        """
        Parse a product item from Rakuten API JSON structure.
        """
        product_name = (
            item.get("itemName")
            or item.get("name")
            or item.get("title")
            or item.get("catchcopy")
        )
        price = item.get("itemPrice") or item.get("price") or item.get("minPrice")
        product_url = item.get("itemUrl") or item.get("affiliateUrl") or item.get("url")
        product_id = item.get("itemCode") or item.get("productId") or item.get("id")

        if not product_name or not price:
            return None

        # Skip ad redirects
        if product_url and "ias.rakuten.co.jp/redirect" in product_url:
            return None

        # Skip duplicates
        if product_id and product_id in self.scraped_product_ids:
            return None
        if product_id:
            self.scraped_product_ids.add(product_id)

        return {
            "product_name": str(product_name).strip()[:500],
            "category": category_name,
            "price": str(price),
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
