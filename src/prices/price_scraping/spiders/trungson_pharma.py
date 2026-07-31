"""
Spider for Trung Son Pharma (trungsoncare.com) - 200+ store Mekong Delta
pharmacy chain (CS-Cart storefront). Category pages are server-rendered grids
that paginate via ?page=N; not every listed card shows an inline price (some
require login/quote), so cards without a price are skipped.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SELECTORS = {
    "card": "div.ty-grid-list__item",
    "name": "a.product-title",
    "price": "span.ty-price-num",
}

PRICE_RE = re.compile(r"[\d,]+")

BASE = "https://trungsoncare.com"
CATEGORIES = [
    "thuoc.html",
    "thuoc-xuong-khop-gout-co-xuong.html",
    "ho-tro-mat-thi-luc.html",
    "cham-soc-be.html",
    "cham-soc-me.html",
    "sua-bot-dinh-duong.html",
    "bang-ve-sinh.html",
    "thuoc-cam.html",
    "thuoc-khang-sinh.html",
    "thuoc-giam-dau-ha-sot.html",
]
MAX_PAGES_PER_CATEGORY = 5


class TrungsonPharmaSpider(scrapy.Spider):
    name = "trungson_pharma"
    allowed_domains = ["trungsoncare.com"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for slug in CATEGORIES:
            yield scrapy.Request(
                f"{BASE}/{slug}",
                callback=self.parse_category,
                meta={"slug": slug, "page": 1},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        page = response.meta["page"]
        cards = response.css(SELECTORS["card"])
        if not cards:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        category = slug.replace(".html", "").replace("-", " ")
        yielded = 0
        for card in cards:
            item = self._parse_card(card, category, scraped_at)
            if item:
                yielded += 1
                yield item

        if yielded and page < MAX_PAGES_PER_CATEGORY:
            yield response.follow(
                f"{BASE}/{slug}?page={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )

    def _parse_card(self, card, category, scraped_at):
        href = card.css(f"{SELECTORS['name']}::attr(href)").get()
        name = card.css(f"{SELECTORS['name']}::attr(title)").get()
        if not href or not name:
            return None

        price_texts = card.css(f"{SELECTORS['price']}::text").getall()
        price_text = next((t for t in price_texts if PRICE_RE.search(t)), None)
        if not price_text:
            return None
        price = price_text.replace(",", "").strip()

        product_id = href.rstrip("/").split("/")[-1] or None

        return {
            "product_id": product_id,
            "product_name": name.strip(),
            "price": price,
            "currency": self.currency,
            "category": category,
            "url": href,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
