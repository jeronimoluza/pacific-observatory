"""
Spider for scraping Doctor OnCall (Malaysia) - https://www.doctoroncall.com.my/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Use Playwright to render WooCommerce category listing pages
2. Extract product data from li.product cards
3. Follow pagination to get more products
"""

import scrapy
import logging
import re
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class DoctorOnCallSpider(scrapy.Spider):
    """
    Playwright spider for Doctor OnCall (Malaysia).
    Renders WooCommerce category pages and extracts product data from cards.
    """

    name = "doctor_oncall"
    allowed_domains = ["www.doctoroncall.com.my"]
    country = "malaysia"
    currency = "MYR"

    CATEGORIES = [
        (
            "https://www.doctoroncall.com.my/pharmacy/health-food-drinks",
            "Health Food & Drinks",
        ),
        (
            "https://www.doctoroncall.com.my/pharmacy/vitamins-supplements",
            "Vitamins & Supplements",
        ),
        ("https://www.doctoroncall.com.my/pharmacy/personal-care", "Personal Care"),
        ("https://www.doctoroncall.com.my/pharmacy/beauty", "Beauty"),
        ("https://www.doctoroncall.com.my/pharmacy/mother-baby", "Mother & Baby"),
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

    def start_requests(self):
        for url, category in self.CATEGORIES:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 5000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 3000),
                    ],
                    "category": category,
                    "page_num": 1,
                },
            )

    async def parse_listing(self, response):
        """Parse category listing page and extract product data from WooCommerce cards."""
        playwright_page = response.meta.get("playwright_page")
        if playwright_page:
            await playwright_page.close()

        category = response.meta.get("category", "Unknown")
        page_num = response.meta.get("page_num", 1)

        logger.info(f"[{category}] Response length: {len(response.text)} chars")

        # Product cards are <section class="product"> on this WooCommerce theme
        product_cards = response.css("section.product, li.product, div.product")
        logger.info(
            f"[{category}] Page {page_num}: Found {len(product_cards)} product cards"
        )

        seen_urls = set()
        for card in product_cards:
            # Extract product name from h3 > a (most reliable on this theme)
            product_name = (
                card.css("h3 a::text").get()
                or card.css("h2 a::text").get()
                or card.css("h2::text").get()
                or card.css("h3::text").get()
            )

            # Extract price from span/p text only (skip script blocks)
            card_texts = card.css("span::text, p::text").getall()
            all_text = " ".join(t.strip() for t in card_texts if t.strip())

            price_text = None
            rm_prices = re.findall(r"RM([\d.,]+)", all_text)
            if rm_prices:
                price_text = rm_prices[0].replace(",", "").rstrip(".")

            # Extract product URL
            product_url = card.css(
                "h3 a::attr(href), h2 a::attr(href), a::attr(href)"
            ).get()
            if product_url and not product_url.startswith("http"):
                product_url = response.urljoin(product_url)

            if not product_name or not price_text:
                continue

            product_name = product_name.strip()
            if product_url and product_url in seen_urls:
                continue
            if product_url:
                seen_urls.add(product_url)

            yield {
                "product_name": product_name,
                "category": category,
                "price": price_text,
                "currency": self.currency,
                "url": product_url or response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        # Pagination
        next_link = response.css("a.next::attr(href)").get()
        if (
            next_link
            and page_num < self.MAX_PAGES_PER_CATEGORY
            and len(product_cards) > 0
        ):
            if not next_link.startswith("http"):
                next_link = response.urljoin(next_link)

            yield scrapy.Request(
                next_link,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded",
                    },
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 5000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight / 2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 3000),
                    ],
                    "category": category,
                    "page_num": page_num + 1,
                },
            )
