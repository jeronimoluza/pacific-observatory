"""Spider for SquareFoot HK rental listings (cards hydrate via AJAX, needs Playwright)."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

SECTIONS = [
    ("rent", "Rent"),
]

HKD_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
MAN_HK_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*萬")
ROOM_RE = re.compile(r"([0-9]+)\s*房")
AREA_RE = re.compile(r"([0-9][0-9,]*)\s*呎")
ID_RE = re.compile(
    r"property-(\d+)|/property/[^/]*/(\d+)|/listing/(\d+)|attr1=[\"'](\d+)", re.I
)


class SquarefootHkSpider(scrapy.Spider):
    name = "squarefoot_hk"
    allowed_domains = ["squarefoot.com.hk"]
    currency = "HKD"
    language = "zh-HK"

    SELECTORS = {
        "card": ".item.property_item, .property_item",
        "link": "img.detail_page::attr(href), a[href*='/property']::attr(href), a[href*='/rent/']::attr(href)",
        "name": "h2::text, h3::text, .title::text, [class*='title']::text, [class*='name']::text",
    }

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    async def start(self):
        for slug, name in SECTIONS:
            url = f"https://www.squarefoot.com.hk/{slug}/"
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 15000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight/3)",
                        ),
                        PageMethod("wait_for_timeout", 5000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight*2/3)",
                        ),
                        PageMethod("wait_for_timeout", 5000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 5000),
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
            joined = " ".join(
                t.strip() for t in card.css("*::text").getall() if t.strip()
            )
            if not joined:
                continue

            product_id = None
            search_str = " ".join(
                card.css("*::attr(href)").getall() + card.css("*::attr(attr1)").getall()
            )
            if href:
                search_str = href + " " + search_str
            m = ID_RE.search(search_str)
            if m:
                product_id = next((g for g in m.groups() if g), None)
            if not product_id:
                product_id = f"sqft-{abs(hash(joined)) % 10**10}"
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
                name = texts[0] if texts else "Unknown"

            price = None
            m_hkd = HKD_RE.search(joined)
            if m_hkd:
                v = m_hkd.group(1).replace(",", "")
                try:
                    if float(v) > 0:
                        price = v
                except ValueError:
                    pass
            if not price:
                m_man = MAN_HK_RE.search(joined)
                if m_man:
                    try:
                        price = f"{float(m_man.group(1)) * 10000:.0f}"
                    except ValueError:
                        pass
            if not price:
                continue

            m_room = ROOM_RE.search(joined)
            bedrooms = m_room.group(1) if m_room else None
            m_area = AREA_RE.search(joined)
            area = m_area.group(1).replace(",", "") if m_area else None

            cat_label = category
            if bedrooms or area:
                bits = []
                if bedrooms:
                    bits.append(f"{bedrooms}BR")
                if area:
                    bits.append(f"{area}sqft")
                cat_label = f"{category} ({', '.join(bits)})"

            url = response.urljoin(href) if href else response.url
            yield {
                "product_id": str(product_id),
                "product_name": name[:500],
                "category": cat_label,
                "price": price,
                "currency": self.currency,
                "available": True,
                "url": url,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            yielded += 1
        logger.info(f"squarefoot_hk: yielded {yielded} cards from {response.url}")
