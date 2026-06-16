"""Spider for HK CSL postpaid mobile plans (tariff source, Playwright for 503-on-curl)."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

START_URLS = [
    "https://www.hkcsl.com/en/service-plan/",
    "https://www.hkcsl-5g.com/en/5g-tariff-plan/",
]

PRICE_RE = re.compile(
    r"(?:Monthly\s+Plan\s+Fee[^$]*?|HK)?\$\s*([0-9][0-9,]{1,5}(?:\.[0-9]+)?)"
)
PLAIN_NUM_RE = re.compile(r"\$\s*([0-9][0-9,]{1,5}(?:\.[0-9]+)?)")


def slugify(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return re.sub(r"-+", "-", s).strip("-")


class CslHkPostpaidSpider(scrapy.Spider):
    name = "csl_hk_postpaid"
    allowed_domains = ["hkcsl.com"]
    currency = "HKD"
    language = "en"

    SELECTORS = {
        "card": ".slick-slide:not(.slick-cloned), [class*='plan-card'], [class*='PlanCard'], .planItem, [class*='tariff-card']",
        "name": "h2::text, h3::text, h4::text, h5::text, .plan-name::text, [class*='title']::text, [class*='planName']::text, strong::text",
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    async def start(self):
        for url in START_URLS:
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                dont_filter=True,
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
                },
            )

    def parse_listing(self, response):
        cards = response.css(self.SELECTORS["card"])
        yielded = 0
        seen_ids = set()
        for card in cards:
            joined = " ".join(
                t.strip() for t in card.css("*::text").getall() if t.strip()
            )
            if not joined or "Monthly Plan Fee" not in joined:
                continue

            price = None
            for m in PLAIN_NUM_RE.finditer(joined):
                v = m.group(1).replace(",", "")
                try:
                    fv = float(v)
                    if 50 <= fv <= 5000:
                        price = v
                        break
                except ValueError:
                    continue
            if not price:
                continue

            name = None
            for sel in self.SELECTORS["name"].split(", "):
                n = card.css(sel).get()
                if n and n.strip() and "$" not in n:
                    name = n.strip()
                    break
            if not name:
                texts = [
                    t.strip()
                    for t in card.css("*::text").getall()
                    if t.strip() and "$" not in t and len(t.strip()) > 3
                ]
                name = texts[0] if texts else None
            if not name:
                name = f"Plan ${price}/mo"

            product_id = slugify(name)[:80] or f"csl-plan-{abs(hash(joined)) % 10**8}"
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            yield {
                "product_id": product_id,
                "product_name": name[:500],
                "category": "Postpaid Plan",
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": response.url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info(f"csl_hk_postpaid: yielded {yielded} plans from {response.url}")
