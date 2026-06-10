"""Spider for Prometheus (prometheus.org.ua) — paid online courses (Tier 2).

Prometheus is Ukraine's leading MOOC platform; its catalogue mixes free MOOCs
with paid professional "Prometheus+" programmes. We collect the paid programmes
(the ones carrying a UAH price tag) as the COICOP 10 (education) layer of the
PPP basket — non-formal adult / professional education priced in UAH.

The catalogue hydrates client-side (the price tags appear only after JS), so a
real Chromium via Playwright is required. Each paid course is an
``a[href*="/prometheus-plus/"]`` wrapping a ``.course-card-plus`` whose title is
in ``.course-card-plus__title`` and whose price is in ``.tag-price`` ("14000 грн").
"""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

CATALOG_URL = "https://prometheus.org.ua/courses-catalog/"

_PRICE_RE = re.compile(r"(\d[\d\s\xa0]*)")
_SLUG_RE = re.compile(r"/prometheus-plus/([^/?#]+)")


class PrometheusSpider(scrapy.Spider):
    name = "prometheus"
    allowed_domains = ["prometheus.org.ua"]
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
            CATALOG_URL,
            callback=self.parse_catalog,
            meta={
                "playwright": True,
                "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                "playwright_page_methods": [
                    PageMethod(
                        "wait_for_selector", ".course-card-plus", timeout=30000
                    ),
                    # The first card fires the selector; the rest hydrate a beat
                    # later, so settle before reading the full catalogue.
                    PageMethod("wait_for_timeout", 5000),
                ],
            },
            errback=self.errback,
        )

    def parse_catalog(self, response):
        # Paid programmes are anchors to /prometheus-plus/<slug> wrapping a card.
        cards = response.css('a[href*="/prometheus-plus/"]')
        logger.info("prometheus: %d prometheus-plus anchors", len(cards))
        yielded = 0
        seen = set()
        for a in cards:
            name = (a.css(".course-card-plus__title::text").get() or "").strip()
            price_raw = a.css(".tag-price::text").get()
            href = a.css("::attr(href)").get()
            if not name or not price_raw or not href:
                continue
            m = _PRICE_RE.search(price_raw)
            if not m:
                continue
            price = re.sub(r"[\s\xa0]", "", m.group(1))
            if not price.isdigit():
                continue
            sm = _SLUG_RE.search(href)
            product_id = sm.group(1) if sm else None
            if product_id in seen:
                continue
            seen.add(product_id)
            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "price": price,
                "currency": self.currency,
                "category": "Online professional course (Prometheus+)",
                "url": response.urljoin(href),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info("prometheus: yielded %d paid courses", yielded)

    def errback(self, failure):
        logger.error("prometheus request failed: %s — %r",
                     failure.request.url, failure.value)
