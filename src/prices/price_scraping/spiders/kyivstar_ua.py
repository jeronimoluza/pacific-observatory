"""Spider for Kyivstar — mobile tariff plans (Tier 2, Playwright).

Kyivstar is Ukraine's largest mobile operator. Its tariff grid at
``kyivstar.ua/tariffs`` is a Next.js app with CSS-module class names
(``TariffCard_card__<hash>``), so selectors match on the stable prefix and a
real Chromium via Playwright is required. Each card links to a per-plan page and
states the recurring price as "<N> грн/міс" ("<N> UAH/mo" in the EN render). We
collect the plans that carry a monthly price as the COICOP 08.3 (mobile
communication services) layer; contract bundles that show only a daily figure
are skipped.
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

URL = "https://kyivstar.ua/tariffs"

# "750 грн/міс" or the EN render "750 UAH/mo".
_MONTHLY_RE = re.compile(
    r"(\d[\d\s\xa0]*)\s*(?:грн|UAH)\s*[/／\\]?\s*(?:міс|mo)", re.IGNORECASE
)
_SLUG_RE = re.compile(r"/tariffs/([^/?#]+)")


class KyivstarUaSpider(scrapy.Spider):
    name = "kyivstar_ua"
    allowed_domains = ["kyivstar.ua"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        yield scrapy.Request(
            URL,
            callback=self.parse,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "commit"},
                "playwright_page_methods": [
                    PageMethod(
                        "wait_for_selector",
                        '[class*="TariffCard_card"]',
                        timeout=45000,
                    ),
                    PageMethod("wait_for_timeout", 5000),
                ],
            },
            errback=self.errback,
        )

    def parse(self, response):
        cards = response.css('[class*="TariffCard_card"]')
        logger.info("kyivstar_ua: %d tariff cards", len(cards))
        yielded = 0
        for c in cards:
            blob = " ".join(t.strip() for t in c.css("::text").getall() if t.strip())
            mm = _MONTHLY_RE.search(blob)
            if not mm:
                continue  # bundle without an inline monthly price
            price = re.sub(r"[\s\xa0]", "", mm.group(1))
            if not price.isdigit():
                continue
            # Title element has a hashed "...itle..." class; fall back to the
            # leading text run before the first metric.
            name = (c.css('[class*="itle"]::text').get() or "").strip()
            if not name:
                name = blob.split("  ")[0][:40].strip()
            href = c.css("a::attr(href)").get()
            sm = _SLUG_RE.search(href or "")
            product_id = sm.group(1) if sm else None
            yield {
                "product_id": product_id,
                "product_name": f"Kyivstar {name}" if name else "Kyivstar tariff",
                "price": price,
                "currency": self.currency,
                "category": "Mobile tariff (per month)",
                "url": response.urljoin(href) if href else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1
        logger.info("kyivstar_ua: yielded %d plans", yielded)

    def errback(self, failure):
        logger.error("kyivstar_ua request failed: %s — %r",
                     failure.request.url, failure.value)
