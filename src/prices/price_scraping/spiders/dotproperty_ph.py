"""Spider for DotProperty Philippines — rental listings via Playwright."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

PROVINCES = [
    "",
    "/metro-manila",
    "/cebu",
    "/cavite",
    "/laguna",
    "/pampanga",
]

PRICE_RE = re.compile(r"₱\s*([0-9][0-9,]*)")
ID_RE = re.compile(r"/ads/([^/?#]+)")


class DotPropertyPhSpider(scrapy.Spider):
    name = "dotproperty_ph"
    allowed_domains = ["dotproperty.com.ph"]
    currency = "PHP"
    language = "en"

    SELECTORS = {
        "card": ".listing-snippet",
        "card_link": 'a[href*="/ads/"]',
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        for prov in PROVINCES:
            url = f"https://www.dotproperty.com.ph/properties-for-rent{prov}"
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
                    "category": prov.strip("/") or "all-ph",
                },
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        cards = response.css(self.SELECTORS["card"])
        yielded = 0
        seen = set()
        for card in cards:
            href = card.css(f'{self.SELECTORS["card_link"]}::attr(href)').get()
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
                t.strip() for t in card.css("*::text").getall() if t.strip()
            )

            price = None
            for pm in PRICE_RE.finditer(card_text):
                raw = pm.group(1).replace(",", "")
                try:
                    if int(raw) > 0:
                        price = raw
                        break
                except ValueError:
                    continue
            if not price:
                continue

            name = None
            for sel in ("h2::text", "h3::text", "h4::text"):
                t = card.css(sel).get()
                if t and t.strip():
                    name = t.strip()
                    break
            if not name:
                slug = product_id.split("_")[0].replace("-", " ").strip()
                name = slug or product_id

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
        logger.info(f"dotproperty_ph: yielded {yielded} cards from {response.url}")
