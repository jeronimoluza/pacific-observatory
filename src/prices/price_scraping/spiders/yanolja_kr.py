"""Spider for Yanolja (Korea) — accommodation aggregator (Tier 2, Playwright)."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

BASE = "https://nol.yanolja.com"

CATEGORIES = [
    ("/sub-home/hotel", "Hotel"),
    ("/sub-home/motel", "Motel"),
    ("/sub-home/pension", "Pension"),
    ("/sub-home/pool-villa", "Pool Villa"),
    ("/around/keyword-hotel?sourcePage=Hotel", "Hotel Search"),
]

PRICE_RE = re.compile(r"([0-9]{1,3}(?:[, ][0-9]{3})+|[0-9]{4,})\s*원")
ID_RE = re.compile(r"/stay/(?:domestic|overseas)/([0-9]+)")


class YanoljaKrSpider(scrapy.Spider):
    name = "yanolja_kr"
    allowed_domains = ["yanolja.com", "nol.yanolja.com"]
    currency = "KRW"
    language = "ko"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        },
        "PLAYWRIGHT_CONTEXTS": {
            "default": {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 720},
            }
        },
    }

    async def start(self):
        for path, name in CATEGORIES:
            url = f"{BASE}{path}"
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
                            "window.scrollTo(0, document.body.scrollHeight/3)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight*2/3)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                    "category": name,
                },
                errback=self.errback,
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        yielded = 0
        seen_ids = set()

        # Cards in next.js components vary; iterate any <a href="/stay/..."> as anchor.
        anchors = response.css('a[href*="/stay/domestic/"], a[href*="/stay/overseas/"]')
        for anchor in anchors:
            href = anchor.css("::attr(href)").get()
            if not href:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            product_id = m.group(1)
            if product_id in seen_ids:
                continue

            # Build a card-scoped text blob: walk up to ancestor card if possible.
            # Use the anchor itself plus its parent for context.
            card_text = " ".join(
                t.strip() for t in anchor.css("*::text").getall() if t.strip()
            )
            # Also fall back to the anchor's parent siblings text
            parent_text = " ".join(
                t.strip()
                for t in anchor.xpath("./parent::*//text()").getall()
                if t.strip()
            )
            joined = f"{card_text} {parent_text}"

            price = None
            for pm in PRICE_RE.finditer(joined):
                v = pm.group(1).replace(",", "").replace(" ", "")
                try:
                    if float(v) > 0:
                        price = v
                        break
                except ValueError:
                    continue
            if not price:
                continue

            # Name: first non-numeric, non-currency, non-percent text node in the anchor.
            all_texts = [t.strip() for t in anchor.css("*::text").getall() if t.strip()]
            name = next(
                (
                    t
                    for t in all_texts
                    if not re.fullmatch(r"[\d,. ]+", t)
                    and "원" not in t
                    and not t.endswith("%")
                ),
                None,
            )
            if not name:
                continue

            seen_ids.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1

        logger.info(f"yanolja_kr: yielded {yielded} cards from {response.url}")

    def errback(self, failure):
        logger.error(f"Request failed: {failure.request.url} — {failure.value!r}")
