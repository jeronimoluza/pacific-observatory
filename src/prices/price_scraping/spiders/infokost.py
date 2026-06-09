"""Spider for Infokost ID — kost (informal rental) listings, Playwright SSR-hydrate."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

CITIES = [
    "jakarta-selatan",
    "jakarta-pusat",
    "bandung",
    "surabaya",
    "depok",
    "tangerang",
]

PRICE_RE = re.compile(r"Rp\s*([0-9][0-9.,]*)")
ID_RE = re.compile(r"/listings/(.+?)(?:[?#]|$)")


class InfokostSpider(scrapy.Spider):
    name = "infokost"
    allowed_domains = ["infokost.id"]
    currency = "IDR"
    language = "id"

    SELECTORS = {
        "card_anchor": 'a[href^="/listings/"]',
        "name": '[class*="font-semibold"], [class*="font-bold"]',
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        for city in CITIES:
            url = f"https://infokost.id/kost/{city}"
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 5000),
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
                    "category": city,
                },
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        anchors = response.css(self.SELECTORS["card_anchor"])
        yielded = 0
        seen = set()
        for a in anchors:
            href = a.css("::attr(href)").get()
            if not href:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            product_id = m.group(1)
            if product_id in seen:
                continue
            seen.add(product_id)

            card_text = " ".join(
                t.strip() for t in a.css("*::text").getall() if t.strip()
            )

            name = None
            for sel in self.SELECTORS["name"].split(", "):
                name = a.css(f"{sel}::text").get()
                if name and name.strip():
                    name = name.strip()
                    break
            if not name:
                alt = a.css("img::attr(alt)").get()
                name = alt.strip() if alt else None
            if not name:
                continue

            price = None
            for pm in PRICE_RE.finditer(card_text):
                raw = pm.group(1).replace(".", "").replace(",", "")
                try:
                    if int(raw) > 0:
                        price = raw
                        break
                except ValueError:
                    continue
            if not price:
                continue

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
        logger.info(f"infokost: yielded {yielded} cards from {response.url}")
