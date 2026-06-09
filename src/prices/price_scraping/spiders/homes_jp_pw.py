"""Spider for Homes.co.jp rental listings using Playwright to bypass AWS WAF challenge."""

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
]

PRICE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*万円")
YEN_RE = re.compile(r"([0-9][0-9,]{3,})\s*円")


class HomesJpPwSpider(scrapy.Spider):
    name = "homes_jp_pw"
    allowed_domains = ["homes.co.jp"]
    currency = "JPY"
    language = "ja"

    SELECTORS = {
        "row": "tr.prg-room[data-kykey], tr.prg-room, [class*='mod-mergeBuilding'] tr, .mod-mergeTable-room",
        "price_num": "td.price span.num::text, td.price::text, [class*='priceLabel']::text",
        "link": "a[href*='/chintai/']::attr(href), a[href*='/room/']::attr(href)",
        "name": "td.bukken a::text, [class*='roomName']::text, td a::text",
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        for slug, name in PREFECTURES:
            url = f"https://www.homes.co.jp/chintai/{slug}/list/"
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
        body_text = response.text.lower()
        if (
            "captcha" in body_text
            or "challenge" in body_text
            or len(response.body) < 5000
        ):
            logger.warning(
                f"homes_jp_pw: possible WAF/challenge page at {response.url} (size={len(response.body)})"
            )

        rows = response.css(self.SELECTORS["row"])
        yielded = 0
        seen_ids = set()
        for row in rows:
            kykey = row.attrib.get("data-kykey")
            href = row.css(self.SELECTORS["link"]).get()
            product_id = kykey or href
            if not product_id:
                continue
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            name = None
            for sel in self.SELECTORS["name"].split(", "):
                n = row.css(sel).get()
                if n and n.strip():
                    name = n.strip()
                    break
            if not name:
                texts = [t.strip() for t in row.css("*::text").getall() if t.strip()]
                name = texts[0] if texts else "Unknown"

            joined = " ".join(
                t.strip() for t in row.css("*::text").getall() if t.strip()
            )
            price = None
            num_text = row.css("td.price span.num::text").get()
            if num_text:
                try:
                    v = float(num_text.strip().replace(",", ""))
                    price = f"{v * 10000:.0f}"
                except ValueError:
                    pass
            if not price:
                m_man = PRICE_RE.search(joined)
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

            url = response.urljoin(href) if href else response.url
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": category,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info(f"homes_jp_pw: yielded {yielded} rows from {response.url}")
