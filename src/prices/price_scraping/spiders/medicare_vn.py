"""Spider for Medicare Vietnam - https://medicare.vn/ (Vue SPA, listing cards)."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

SELECTORS = {
    "card": ".grid-item.card",
    "link": ".product-name a[href*='/products/']",
    "name": ".product-name a",
    "price": "span.product-price",
}

CATEGORIES = [
    ("pharmaceutical-69631", "Pharmaceuticals"),
    ("health-68173", "Health & Wellness"),
    ("vitamins-supplements-69085", "Vitamins & Supplements"),
    ("personal-care-68133", "Personal Care"),
    ("skincare-68414", "Skincare"),
    ("cosmetics-68520", "Makeup"),
    ("hair-68304", "Hair Care"),
    ("baby-68338", "Baby Products"),
    ("men-68123", "Men's Products"),
]

PRICE_RE = re.compile(r"([0-9][0-9\.,]{2,})\s*(?:₫|đ|VND)", re.IGNORECASE)
ID_RE = re.compile(r"/products/([^/?#]+)")


class MedicareVnSpider(scrapy.Spider):
    name = "medicare_vn"
    allowed_domains = ["medicare.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        for slug, name in CATEGORIES:
            url = f"https://medicare.vn/products?category={slug}"
            yield scrapy.Request(
                url,
                callback=self.parse_listing,
                meta={
                    "playwright": True,
                    "playwright_page_goto_kwargs": {"wait_until": "domcontentloaded"},
                    "playwright_page_methods": [
                        PageMethod("wait_for_timeout", 8000),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight/3)",
                        ),
                        PageMethod("wait_for_timeout", 2500),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight*2/3)",
                        ),
                        PageMethod("wait_for_timeout", 2500),
                        PageMethod(
                            "evaluate",
                            "window.scrollTo(0, document.body.scrollHeight)",
                        ),
                        PageMethod("wait_for_timeout", 2500),
                    ],
                    "category": name,
                },
                dont_filter=True,
            )

    def parse_listing(self, response):
        category = response.meta.get("category")
        cards = response.css(SELECTORS["card"])
        yielded = 0
        seen_ids = set()
        for card in cards:
            href = card.css(SELECTORS["link"] + "::attr(href)").get()
            if not href:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            product_id = m.group(1)
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            name = card.css(SELECTORS["name"] + "::text").get()
            if not name or not name.strip():
                name = card.css("img::attr(alt)").get()
            if not name or not name.strip():
                continue
            name = name.strip()

            joined = " ".join(
                t.strip() for t in card.css("*::text").getall() if t.strip()
            )
            price = None
            for m2 in PRICE_RE.finditer(joined):
                v = m2.group(1).replace(".", "").replace(",", "")
                try:
                    if float(v) > 0:
                        price = v
                        break
                except ValueError:
                    continue
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
        logger.info(f"medicare_vn: yielded {yielded} cards from {response.url}")
