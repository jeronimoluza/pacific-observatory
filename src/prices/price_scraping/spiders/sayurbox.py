"""Spider for Sayurbox Indonesia - https://www.sayurbox.com/ (React Native Web SPA)."""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

SELECTORS = {
    "card": "[data-testid^='qa_product_']",
    "link": "a[data-testid='sb_link_product_detail']",
}

NAME_SKIP_PREFIXES = ("Rp", "Promo ", "Diskon", "Syarat", "Tambah", "Habis")

CATEGORIES = [
    ("vegetables-1-a0d03d59", "Vegetables"),
    ("fruits-1-cdd2074a", "Fruits"),
    ("ayamdandaging-cuqvifmj", "Meat & Poultry"),
    ("ikanseafood-1-a9d498d8", "Fish & Seafood"),
    ("susuolahansusu-1-6ca61e96", "Dairy"),
    ("telurtahutempe-ocbxufxq", "Eggs Tofu Tempe"),
    ("sembako-1-e6a33b51", "Staples"),
    ("bumbudapurdankue-1-7b6d1a50", "Spices & Baking"),
    ("makananringan-1-b937f45a", "Snacks"),
    ("kopitehminuman-1-3c8f6ecc", "Coffee Tea Drinks"),
]

PRICE_RE = re.compile(r"^Rp\s*([0-9][0-9\.,]{2,})$")
ID_RE = re.compile(r"^qa_product_(.+)$")


class SayurboxSpider(scrapy.Spider):
    name = "sayurbox"
    allowed_domains = ["sayurbox.com"]
    currency = "IDR"
    language = "id"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    async def start(self):
        for slug, name in CATEGORIES:
            url = f"https://www.sayurbox.com/category/{slug}"
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
            testid = card.css("::attr(data-testid)").get() or ""
            m = ID_RE.match(testid)
            if not m:
                continue
            product_id = m.group(1)
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            texts = [t.strip() for t in card.css("*::text").getall() if t.strip()]
            if not texts:
                continue

            price = None
            for t in texts:
                m2 = PRICE_RE.match(t)
                if not m2:
                    continue
                v = m2.group(1).replace(".", "").replace(",", "")
                try:
                    if float(v) > 0:
                        price = v
                        break
                except ValueError:
                    continue
            if not price:
                continue

            name = None
            for t in texts:
                if any(t.startswith(p) for p in NAME_SKIP_PREFIXES):
                    continue
                if len(t) < 4 or t.isdigit():
                    continue
                name = t
                break
            if not name:
                continue

            href = card.css(SELECTORS["link"] + "::attr(href)").get()
            url = (
                response.urljoin(href)
                if href
                else (f"https://www.sayurbox.com/product/{product_id}")
            )

            yield {
                "product_id": product_id,
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
        logger.info(f"sayurbox: yielded {yielded} cards from {response.url}")
