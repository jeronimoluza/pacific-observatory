"""
Spider for scraping K24Klik (Indonesia) - https://www.k24klik.com/
Extracts product information including prices, categories, and URLs.

Strategy:
1. Use Playwright to render JS-heavy category listing pages
2. Extract product data from .product cards on listing pages
3. Follow pagination to get more products
"""

import scrapy
import logging
import re
import hashlib
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class K24KlikSpider(scrapy.Spider):
    """
    Playwright spider for K24Klik (Indonesia).
    Renders category listing pages and extracts product data from cards.
    """

    name = "k24klik"
    allowed_domains = ["www.k24klik.com"]
    currency = "IDR"

    CATEGORIES = [
        ("https://www.k24klik.com/cariObat/vitamin?kategori=true", "Vitamin"),
        ("https://www.k24klik.com/cariObat/obat-batuk?kategori=true", "Obat Batuk"),
        ("https://www.k24klik.com/cariObat/obat-flu?kategori=true", "Obat Flu"),
        ("https://www.k24klik.com/cariObat/obat-maag?kategori=true", "Obat Maag"),
        ("https://www.k24klik.com/cariObat/obat-diare?kategori=true", "Obat Diare"),
        ("https://www.k24klik.com/cariObat/obat-mata?kategori=true", "Obat Mata"),
        (
            "https://www.k24klik.com/cariObat/obat-sakit-kepala?kategori=true",
            "Obat Sakit Kepala",
        ),
        (
            "https://www.k24klik.com/cariObat/perawatan-kulit?kategori=true",
            "Perawatan Kulit",
        ),
        ("https://www.k24klik.com/cariObat/susu-formula?kategori=true", "Susu Formula"),
        (
            "https://www.k24klik.com/cariObat/alat-kesehatan?kategori=true",
            "Alat Kesehatan",
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
                        PageMethod("wait_for_timeout", 2000),
                    ],
                    "category": category,
                    "page_num": 1,
                },
            )

    async def parse_listing(self, response):
        """Parse category listing page and extract product data from cards."""
        playwright_page = response.meta.get("playwright_page")
        if playwright_page:
            await playwright_page.close()

        category = response.meta.get("category", "Unknown")
        page_num = response.meta.get("page_num", 1)

        logger.info(f"[{category}] Response length: {len(response.text)} chars")

        product_cards = response.css("li.product")
        logger.info(
            f"[{category}] Page {page_num}: Found {len(product_cards)} product cards"
        )

        seen_urls = set()
        for card in product_cards:
            # Extract product name from img alt (most reliable) or h5 text
            product_name = card.css("img.lazy::attr(alt)").get()
            if product_name and product_name.startswith("Apotek Online - "):
                product_name = product_name.replace("Apotek Online - ", "")
            if not product_name:
                product_name = card.css("h5::text").get()

            # Extract price from text (skip style blocks)
            card_texts = card.css("p::text, span::text, h5::text").getall()
            all_text = " ".join(t.strip() for t in card_texts if t.strip())

            price_text = None
            price_match = re.search(r"Rp\s*([\d.,]+)", all_text)
            if price_match:
                price_text = price_match.group(1).replace(".", "").replace(",", "")

            # Extract product URL
            product_url = card.css("a::attr(href)").get()
            if product_url and product_url.startswith("javascript"):
                product_url = None
            if product_url and not product_url.startswith("http"):
                product_url = response.urljoin(product_url)

            if not product_name or not price_text:
                continue

            if product_url and product_url in seen_urls:
                continue
            if product_url:
                seen_urls.add(product_url)

            # Create url_hash using both product_name and url since all products
            # are listed on the same category URLs
            url_for_hash = product_url or response.url
            hash_input = f"{product_name.strip()}|{url_for_hash}"
            url_hash = hashlib.md5(hash_input.encode()).hexdigest()

            yield {
                "product_name": product_name.strip(),
                "category": category,
                "price": price_text,
                "currency": self.currency,
                "url": url_for_hash,
                "url_hash": url_hash,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        # Pagination - check for next page link
        if page_num < self.MAX_PAGES_PER_CATEGORY and len(product_cards) > 0:
            next_page = page_num + 1
            base_url = response.url.split("&page=")[0].split("?page=")[0]
            separator = "&" if "?" in base_url else "?"
            next_url = f"{base_url}{separator}page={next_page}"

            yield scrapy.Request(
                next_url,
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
                        PageMethod("wait_for_timeout", 2000),
                    ],
                    "category": category,
                    "page_num": next_page,
                },
            )
