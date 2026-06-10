"""Spider for Hotline.finance — Ukraine insurance premiums (Tier 2, Playwright).

Hotline.finance is Ukraine's dominant insurance-comparison portal. Each product
page (OSAGO, KASKO, Green Card, travel) renders a "price by geography" widget:
one card per city showing the aggregated premium range across insurers, e.g.
"Київ 4687 грн – 7057 грн · 13 пропозицій". We capture the *from* (cheapest)
premium per city as the COICOP 12.1 (insurance) layer of the PPP basket — the
one division otherwise unreachable (insurer sites are calculator-gated).

Because it reports the minimum offer across many insurers, analytical_role is
aggregate_proxy. The widget hydrates client-side, so Playwright is required.
Cards are ``.price-by-geo-card--slide``; each wraps a city link
(``/ua/<product>-<city>``) and a text blob "<city><min> грн - <max> грн...".
"""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

_BASE = "https://hotline.finance"

# product path -> stable English insurance-type label (all COICOP 12.1).
# Only the pages that expose the "price by geography" widget are listed; KASKO
# and Green Card render a calculator instead (no per-city premium cards).
PRODUCTS = [
    ("/ua/osago", "OSAGO (compulsory motor third-party liability)"),
    ("/ua/insurance-travel", "Travel insurance"),
]

_PRICE_RE = re.compile(r"(\d[\d\s\xa0]*)\s*грн")
_CITY_SPLIT_RE = re.compile(r"\d")


class HotlineFinanceSpider(scrapy.Spider):
    name = "hotline_finance"
    allowed_domains = ["hotline.finance"]
    currency = "UAH"
    language = "uk"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        for path, label in PRODUCTS:
            yield scrapy.Request(
                f"{_BASE}{path}",
                callback=self.parse_product,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {
                        "wait_until": "domcontentloaded"
                    },
                    "playwright_page_methods": [
                        PageMethod(
                            "wait_for_selector",
                            ".price-by-geo-card--slide",
                            timeout=25000,
                        ),
                        PageMethod("wait_for_timeout", 3000),
                    ],
                    "insurance_type": label,
                },
                errback=self.errback,
            )

    def parse_product(self, response):
        label = response.meta.get("insurance_type")
        cards = response.css(".price-by-geo-card--slide")
        logger.info("hotline_finance: %s -> %d geo cards", label, len(cards))
        yielded = 0
        for c in cards:
            blob = " ".join(t.strip() for t in c.css("::text").getall() if t.strip())
            href = c.css("a::attr(href)").get()
            prices = _PRICE_RE.findall(blob)
            if not prices:
                continue
            # First (cheapest / "from") premium in the min–max range.
            price = re.sub(r"[\s\xa0]", "", prices[0])
            if not price.isdigit():
                continue
            city = _CITY_SPLIT_RE.split(blob, 1)[0].strip() or None
            product_id = (
                href.strip("/").split("/")[-1] if href else None
            )
            yield {
                "product_id": product_id,
                "product_name": f"{label} — {city}" if city else label,
                "price": price,
                "currency": self.currency,
                "category": f"Insurance premium (from) — {label}",
                "url": response.urljoin(href) if href else response.url,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info("hotline_finance: yielded %d from %s", yielded, label)

    def errback(self, failure):
        logger.error("hotline_finance request failed: %s — %r",
                     failure.request.url, failure.value)
