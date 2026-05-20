"""
Spider for SmartDoko (Nepal) - https://smartdoko.com/

Listing-card extraction with Playwright. Product cards on category pages carry
name + price + canonical /product/<slug> URL via schema.org microdata.
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class SmartdokoSpider(scrapy.Spider):
    name = "smartdoko"
    allowed_domains = ["smartdoko.com"]
    currency = "NPR"

    START_URLS = [
        "https://smartdoko.com/category/fresh-foods",
        "https://smartdoko.com/category/dairy-product",
        "https://smartdoko.com/category/frozen-items",
        "https://smartdoko.com/category/bakery",
        "https://smartdoko.com/category/baking-cooking",
        "https://smartdoko.com/category/baby-mother-care-110",
        "https://smartdoko.com/category/baby-creams",
        "https://smartdoko.com/category/baby-soap",
        "https://smartdoko.com/category/baby-shampoo",
        "https://smartdoko.com/category/vitamins-dietary-supplements-1343",
        "https://smartdoko.com/category/air-conditioners",
        "https://smartdoko.com/category/air-fryers",
        "https://smartdoko.com/category/audio",
        "https://smartdoko.com/category/4k-tv",
        "https://smartdoko.com/category/washing-machine",
        "https://smartdoko.com/category/water-purifier-2567",
        "https://smartdoko.com/category/water-dispensers",
        "https://smartdoko.com/category/vacuum-cleaners",
        "https://smartdoko.com/category/wines-353",
        "https://smartdoko.com/category/alcohols-315",
    ]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    PRICE_RE = re.compile(r"[\d,]+\.?\d*")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls: set[str] = set()

    def start_requests(self):
        for url in self.START_URLS:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 6000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight/2)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate", "window.scrollTo(0, document.body.scrollHeight)"
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
            )

    def parse_listing(self, response):
        cards = response.css("div.product-box div.product")
        logger.info(f"smartdoko: {response.url} → {len(cards)} product cards")
        for card in cards:
            href = card.css("a[href^='/product/']::attr(href)").get()
            if not href:
                continue
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)

            name = (
                card.css("h4 a::attr(title)").get()
                or card.css("h4 a::text").get()
                or card.css("a[itemprop='name'] img::attr(alt)").get()
            )
            price_text = card.css("span[itemprop='price']::text").get() or ""
            price = None
            if price_text:
                m = self.PRICE_RE.search(price_text.replace(",", ""))
                if m:
                    price = m.group(0)

            if not name or not price:
                continue

            yield {
                "product_id": None,
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
