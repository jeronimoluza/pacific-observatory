"""Spider for Vodafone Ukraine — mobile tariff plans (Tier 2, Playwright).

Vodafone is one of Ukraine's three mobile operators. Its tariff grid at
``vodafone.ua/tariffs`` is an Angular app: the plan cards (``.vf-tariff-card``)
hydrate client-side, so a real Chromium via Playwright is required. Each card
carries a plan name, a recurring price ("420 грн") and a billing period
("на 4 тижні" / "на місяць"). We collect the standalone mobile plans as the
COICOP 08.3 (telephone & telefax / mobile communication services) layer — the
one division otherwise represented only by ICT *equipment*.

The first card is the subscriber's "my tariff" account widget (no price); cards
without a parseable price are skipped.
"""

import logging
import re

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

URL = "https://www.vodafone.ua/tariffs"

# The grid renders in whichever language the browser advertises (scrapy-playwright
# defaults to English -> "420 UAH per 4 weeks"; a uk client gets "420 грн на
# 4 тижні"), so price and period are matched bilingually.
_PRICE_RE = re.compile(r"(\d[\d\s\xa0]*)\s*(?:грн|UAH|₴)", re.IGNORECASE)
_PERIOD_RE = re.compile(
    r"(?:на\s+[\w\s]+?(?:тиж\w*|місяц\w*|день|дн\w*)"
    r"|per\s+\d*\s*(?:week|month|day)s?)",
    re.IGNORECASE,
)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class VodafoneUaSpider(scrapy.Spider):
    name = "vodafone_ua"
    allowed_domains = ["vodafone.ua"]
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
                # The Angular app can stall past a domcontentloaded timeout, so
                # return on "commit" and let wait_for_selector gate on hydration.
                "playwright_page_goto_kwargs": {"wait_until": "commit"},
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", ".vf-tariff-card", timeout=45000),
                    PageMethod("wait_for_timeout", 3000),
                ],
            },
            errback=self.errback,
        )

    def parse(self, response):
        cards = response.css(".vf-tariff-card")
        logger.info("vodafone_ua: %d tariff cards", len(cards))
        yielded = 0
        for c in cards:
            name = (c.css('[class*="title"]::text').get() or "").strip()
            blob = " ".join(t.strip() for t in c.css("::text").getall() if t.strip())
            pm = _PRICE_RE.search(blob)
            if not name or not pm:
                continue  # account widget / unpriced card
            price = re.sub(r"[\s\xa0]", "", pm.group(1))
            if not price.isdigit():
                continue
            period = _PERIOD_RE.search(blob)
            period = period.group(0).strip() if period else None
            slug = _SLUG_RE.sub("-", name.lower()).strip("-")
            yield {
                "product_id": f"vodafone-{slug}" if slug else None,
                "product_name": f"Vodafone {name}",
                "price": price,
                "currency": self.currency,
                "category": f"Mobile tariff ({period})" if period else "Mobile tariff",
                # All plan cards share the page URL; add a per-plan fragment so
                # the URL-dedup pipeline keeps each plan.
                "url": f"{response.url}#{slug}" if slug else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
            yielded += 1
        logger.info("vodafone_ua: yielded %d plans", yielded)

    def errback(self, failure):
        logger.error("vodafone_ua request failed: %s — %r",
                     failure.request.url, failure.value)
