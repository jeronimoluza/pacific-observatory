"""
Spider for Central Online (Thailand) - https://www.central.co.th/
Listing-card extraction with Playwright. The category page renders products
inline with brand, name, and ฿ price; no PDP visits (Central's PDPs throw a
Cloudflare challenge on second-pageload from a non-residential IP, but the
category listing renders cleanly).
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)


class CentralThSpider(scrapy.Spider):
    name = "central_th"
    allowed_domains = ["central.co.th", "www.central.co.th"]
    currency = "THB"

    # Sample categories covering beauty, home, and lifestyle. Listing pages
    # render ~30 products each; this is enough for a representative price feed.
    START_URLS = [
        "https://www.central.co.th/th/beauty/bath-body/bath-shower",
        "https://www.central.co.th/th/beauty/bath-body/body-scrub",
        "https://www.central.co.th/th/home-lifestyle/cooking-dining/drinkware/insulated-bottles-tumblers",
    ]

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS": 1,
    }

    PRICE_RE = re.compile(r"[\d,.]+")
    # PDP slug ends with `-cds<digits>` (canonical product ID).
    PDP_HREF_RE = re.compile(r"^/th/.+-cds\d{6,}$")

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
        # Central renders each product as two anchors to the same PDP — one
        # wraps the image (text content = discount badge like "-10%") and one
        # uses `class="line-clamp-2 ..."` containing the real product name in
        # Thai. We only want the name anchor.
        name_anchors = response.css("a.line-clamp-2[href*='cds']")
        cards_found = 0
        for a in name_anchors:
            href = a.attrib.get("href", "")
            if not self.PDP_HREF_RE.match(href):
                continue
            url = response.urljoin(href)
            if url in self.seen_urls:
                continue

            text = (a.css("::text").get() or "").strip()
            if not text:
                continue
            # The price node (`p.text-central-red`) lives in a sibling block
            # within the same card container. Walk up to a stable ancestor.
            card = a.xpath("ancestor::div[contains(@class, 'relative w-full')][1]")
            if not card:
                card = a.xpath("ancestor::div[1]")
            price_text = card.css("p.text-central-red::text").get() or ""
            if not price_text:
                continue

            price = None
            m = self.PRICE_RE.search(price_text.replace("฿", "").strip())
            if m:
                price = m.group(0)
            if not price:
                continue

            self.seen_urls.add(url)
            cards_found += 1

            pid_m = re.search(r"-(cds\d+)$", href)
            product_id = pid_m.group(1) if pid_m else None

            yield {
                "product_id": product_id,
                "product_name": text,
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
        logger.info(f"central_th: yielded {cards_found} cards from {response.url}")
