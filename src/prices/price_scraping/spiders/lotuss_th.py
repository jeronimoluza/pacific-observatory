"""
Spider for Lotus's Thailand - https://www.lotuss.com/th/
Listing-card extraction with Playwright. Category pages are MUI/React; cards
hydrate as `.MuiCard-root` containers, each holding an
  <a id="product-card-..." href="/th/product/<id>">
plus product name and ฿THB price as plain card text. No PDP visits needed.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy
from scrapy_playwright.page import PageMethod

logger = logging.getLogger(__name__)

CATEGORIES = [
    ("milk-and-beverages-1", "Milk & Beverages"),
    ("fresh-food-deal", "Fresh Food"),
    ("dried-food-and-ingredients-1", "Dried Food & Ingredients"),
    ("snacks-and-desserts-1", "Snacks & Desserts"),
    ("mom-and-baby", "Mom & Baby"),
    ("household-and-merits", "Household"),
    ("beauty-and-personal-care", "Beauty & Personal Care"),
    ("only-at-lotus-s", "Only at Lotus's"),
    ("PETFOODANDSUPPLIES", "Pet Food & Supplies"),
]

PRICE_RE = re.compile(r"([0-9,]+\.[0-9]{2})")
ID_RE = re.compile(r"/th/product/(.+?)(?:[?#]|$)")


class LotussThSpider(scrapy.Spider):
    name = "lotuss_th"
    allowed_domains = ["lotuss.com"]
    currency = "THB"
    language = "th"

    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 1,
    }

    def start_requests(self):
        for slug, name in CATEGORIES:
            url = f"https://www.lotuss.com/th/category/{slug}"
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
        cards = response.css(".MuiCard-root")
        yielded = 0
        seen_ids = set()
        for card in cards:
            href = (
                card.css('a[id^="product-card-"]::attr(href)').get()
                or card.css('a[href*="/th/product/"]::attr(href)').get()
            )
            if not href:
                continue
            m = ID_RE.search(href)
            if not m:
                continue
            product_id = m.group(1)
            if product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            name = card.css("img::attr(alt)").get()
            if not name or not name.strip():
                continue
            name = name.strip()

            joined = " ".join(
                t.strip() for t in card.css("*::text").getall() if t.strip()
            )
            price = None
            for m2 in PRICE_RE.finditer(joined):
                v = m2.group(1).replace(",", "")
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
        logger.info(f"lotuss_th: yielded {yielded} cards from {response.url}")
