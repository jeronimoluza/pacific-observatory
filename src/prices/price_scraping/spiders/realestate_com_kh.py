"""Spider for Realestate.com.kh — rental listings via Playwright."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

AREAS = [
    "",
    "phnom-penh",
    "siem-reap",
    "sihanoukville",
]

PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
ID_RE = re.compile(r"/rent/[a-z0-9-]+/[a-z0-9-]+-(\d+)/?")


class RealestateComKhSpider(scrapy.Spider):
    name = "realestate_com_kh"
    allowed_domains = ["realestate.com.kh"]
    currency = "USD"
    language = "en"

    SELECTORS = {
        "card_anchor": 'a[href^="/rent/"]',
        "save_button": "button[displayrent]",
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        for area in AREAS:
            url = (
                f"https://www.realestate.com.kh/rent/{area}/"
                if area
                else "https://www.realestate.com.kh/rent/"
            )
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
                    "category": area or "all-kh",
                },
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        yielded = 0
        seen = set()

        # Primary: extract from the save-button attribute payloads (one per listing).
        for btn in response.css(self.SELECTORS["save_button"]):
            product_id = btn.attrib.get("id")
            if not product_id or product_id in seen:
                continue
            display_rent = btn.attrib.get("displayrent") or ""
            headline = btn.attrib.get("headline") or ""
            category_name = btn.attrib.get("categoryname") or ""
            address = btn.attrib.get("address") or ""

            pm = PRICE_RE.search(display_rent)
            if not pm:
                continue
            price = pm.group(1).replace(",", "")

            name = headline.strip() or f"{category_name} at {address}".strip()
            if not name:
                continue
            seen.add(product_id)

            url = response.urljoin(f"/rent/listing-{product_id}/")
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": category_name or category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1

        # Fallback: anchor-based extraction (used if save-button selector misses).
        if yielded == 0:
            for a in response.css(self.SELECTORS["card_anchor"]):
                href = a.css("::attr(href)").get()
                if not href:
                    continue
                m = ID_RE.search(href)
                if not m:
                    continue
                product_id = m.group(1)
                if product_id in seen:
                    continue
                title = (a.css("::text").get() or "").strip()
                if not title:
                    continue
                seen.add(product_id)
                yield {
                    "product_id": product_id,
                    "product_name": title[:500],
                    "category": category,
                    "price": None,
                    "currency": self.currency,
                    "available": True,
                    "url": response.urljoin(href),
                    "language": self.language,
                    "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
                }

        logger.info(f"realestate_com_kh: yielded {yielded} cards from {response.url}")
