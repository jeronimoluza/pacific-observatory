"""
Spider for Gourmet Market Online (Thailand) - https://www.gourmetmarketthailand.com/
Listing-card extraction with Playwright. The category page renders product
cards inline with name + price; no PDP visits required.
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class GourmetMarketThSpider(scrapy.Spider):
    name = "gourmet_market_th"
    allowed_domains = ["gourmetmarketthailand.com", "www.gourmetmarketthailand.com"]
    currency = "THB"

    # Each category slug pulled from the homepage cateModal — they end in a
    # numeric category code. Pick a small breadth-representative set; pagination
    # can be added later if more coverage is needed.
    START_URLS = [
        "https://www.gourmetmarketthailand.com/th/100-juice-10602101",
        "https://www.gourmetmarketthailand.com/th/uht-milk-11002",
        "https://www.gourmetmarketthailand.com/th/tea-10604",
        "https://www.gourmetmarketthailand.com/th/water-10608",
        "https://www.gourmetmarketthailand.com/th/yogurt-10703",
    ]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    PRICE_RE = re.compile(r"[\d,.]+")
    # PDP slug ends with a 10+ digit barcode (e.g. 8853333010107). Category
    # slugs end with a shorter 5-8 digit code without a leading underscore.
    PDP_HREF_RE = re.compile(r"^/th/[a-z0-9_\-]+_\d{10,}$")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_urls: set[str] = set()

    async def start(self):
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
            )

    def parse_listing(self, response):
        cards = response.css("div.item-card")
        logger.info(f"gourmet_market_th: found {len(cards)} cards at {response.url}")
        for card in cards:
            href = card.css("a.item-card-detail::attr(href)").get()
            if not href or not self.PDP_HREF_RE.match(href):
                continue
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue
            self.seen_urls.add(url)

            # Image alt is the most stable name source on this site; the
            # .name div carries the same text in Thai.
            name = (
                card.css("a.item-card-detail .name::text").get()
                or card.css("img::attr(alt)").get()
            )
            price_text = (
                card.css("a.item-card-detail .price-per-unit .price::text").get() or ""
            )

            price = None
            if price_text:
                m = self.PRICE_RE.search(price_text.replace("฿", "").strip())
                if m:
                    price = m.group(0)

            if not name or not price:
                continue

            # The trailing numeric block in the slug is the product barcode/EAN.
            pid_m = re.search(r"_(\d{10,})$", href)
            product_id = pid_m.group(1) if pid_m else None

            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
