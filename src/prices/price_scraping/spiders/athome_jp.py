"""Spider for AtHome.co.jp rental listings (JP rentals, Playwright-rendered)."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

PREFECTURES = [
    ("tokyo", "Tokyo"),
    ("osaka", "Osaka"),
    ("kanagawa", "Kanagawa"),
    ("saitama", "Saitama"),
    ("chiba", "Chiba"),
    ("aichi", "Aichi"),
]

MAN_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*万円")
YEN_RE = re.compile(r"([0-9][0-9,]{2,})\s*円")
ID_RE = re.compile(r"/(chintai/[A-Za-z0-9_\-/]+?)(?:[?#]|/?$)")


class AthomeJpSpider(scrapy.Spider):
    name = "athome_jp"
    allowed_domains = ["athome.co.jp"]
    currency = "JPY"
    language = "ja"

    SELECTORS = {
        "card": "[class*='p-property__room--detail-information']",
        "link": "a[href*='/chintai/']::attr(href)",
        "name": "h2::text, h3::text, .property-name::text, [class*='title']::text",
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,
        "DOWNLOAD_DELAY": 4,
        "CONCURRENT_REQUESTS": 1,
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    async def start(self):
        for slug, name in PREFECTURES:
            url = f"https://www.athome.co.jp/chintai/{slug}/list/"
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
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        cards = response.css(self.SELECTORS["card"])
        yielded = 0
        seen_ids = set()
        for card in cards:
            href = card.css(self.SELECTORS["link"]).get()
            if not href:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            product_id = m.group(1)
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            name = None
            for sel in self.SELECTORS["name"].split(", "):
                n = card.css(sel).get()
                if n and n.strip():
                    name = n.strip()
                    break
            if not name:
                texts = [t.strip() for t in card.css("*::text").getall() if t.strip()]
                name = texts[0] if texts else None
            if not name:
                continue

            joined = " ".join(
                t.strip() for t in card.css("*::text").getall() if t.strip()
            )
            price = None
            m_man = MAN_RE.search(joined)
            if m_man:
                try:
                    price = f"{float(m_man.group(1)) * 10000:.0f}"
                except ValueError:
                    pass
            if not price:
                m_yen = YEN_RE.search(joined)
                if m_yen:
                    v = m_yen.group(1).replace(",", "")
                    try:
                        if float(v) > 0:
                            price = v
                    except ValueError:
                        pass
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
        logger.info(f"athome_jp: yielded {yielded} cards from {response.url}")
