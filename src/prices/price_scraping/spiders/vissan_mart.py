"""
Spider for Vissan Mart (vissanmart.com) - Vietnam's national meat processor's
Magento storefront. Server-rendered category grids covering fresh/processed
meat (VietGAP-certified), paginated via ?p=N.
"""

import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SELECTORS = {
    "card": "li.product-item",
    "name": "a.product-item-link",
    "price_box": "div.price-box",
    "price_amount": "span[data-price-amount]",
}

CATEGORIES = [
    "thuc-pham-tuoi-song.html",
    "thuc-pham-che-bien.html",
]
BASE = "https://vissanmart.com/"
MAX_PAGES_PER_CATEGORY = 15


class VissanMartSpider(scrapy.Spider):
    name = "vissan_mart"
    allowed_domains = ["vissanmart.com"]
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
                BASE + slug,
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
                f"{BASE}{slug}?p={page + 1}",
                callback=self.parse_category,
                meta={"slug": slug, "page": page + 1},
            )

    def _parse_card(self, card, category, scraped_at):
        href = card.css(f"{SELECTORS['name']}::attr(href)").get()
        name = card.css(f"{SELECTORS['name']}::text").get()
        if not href or not name or not name.strip():
            return None

        price_box = card.css(SELECTORS["price_box"])
        product_id = price_box.attrib.get("data-product-id")
        price = price_box.css(
            f"{SELECTORS['price_amount']}::attr(data-price-amount)"
        ).get()
        if not price:
            return None

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
