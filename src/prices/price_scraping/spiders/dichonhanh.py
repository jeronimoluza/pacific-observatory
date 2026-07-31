"""
Spider for Di Cho Nhanh (dichonhanh.vn) - Vietnam wet-market-style online
grocer sourcing from HCMC's Binh Dien wholesale market. Server-rendered
category pages (no client-side hydration needed); each /nhom-san-pham/<slug>/
page lists its full product set with name + current price inline.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SELECTORS = {
    "card": "div.product-block",
    "link": "a",
    "name": "div.__name",
    "price": "div.__price span.__current",
}

PRICE_RE = re.compile(r"([\d.,]+)")

BASE = "https://www.dichonhanh.vn"
CATEGORIES = [
    "gia-suc-gia-cam-1",  # livestock/poultry
    "thit-heo-134",  # pork
    "thit-bo-4",  # beef
    "thit-ga-2-2",  # chicken
    "thit-vit-2-3",  # duck
    "hai-san-39",  # seafood
    "thuy-hai-san-14",  # aquatic seafood
    "thuy-san-2-25",  # aquaculture
    "tom-muc-17",  # shrimp/squid
    "ca-nuoc-man-18",  # saltwater fish
    "ca-nuoc-ngot-19",  # freshwater fish
    "rau-an-la-68",  # leafy vegetables
    "rau-xanh-trai-cay-28",  # veg & fruit
    "trai-cay-3-61",  # fruit
    "cu-qua-bap-69",  # tubers/corn
    "rau-nem-khac-60",  # misc vegetables/herbs
    "thit-uop-144",  # marinated meat
    "ca-uop-141",  # marinated fish
    "kho-mam-15",  # dried fish/preserves
    "gia-vi-204",  # condiments
]


class DichonhanhSpider(scrapy.Spider):
    name = "dichonhanh"
    allowed_domains = ["dichonhanh.vn"]
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
                f"{BASE}/nhom-san-pham/{slug}/",
                callback=self.parse_category,
                meta={"slug": slug},
            )

    def parse_category(self, response):
        slug = response.meta["slug"]
        cards = response.css(SELECTORS["card"])
        if not cards:
            logger.info("dichonhanh: no products for slug=%s", slug)
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in cards:
            item = self._parse_card(card, slug, scraped_at)
            if item:
                yield item

    def _parse_card(self, card, slug, scraped_at):
        href = card.css(f"{SELECTORS['link']}::attr(href)").get()
        name = card.css(f"{SELECTORS['name']}::text").get()
        price_text = card.css(f"{SELECTORS['price']}::text").get()
        if not href or not name or not price_text:
            return None

        price_match = PRICE_RE.search(price_text)
        if not price_match:
            return None
        price = price_match.group(1).replace(".", "").replace(",", "")

        product_id = href.strip("/").split("/")[-1] or None

        return {
            "product_id": product_id,
            "product_name": name.strip(),
            "price": price,
            "currency": self.currency,
            "category": slug,
            "url": f"{BASE}{href}" if href.startswith("/") else href,
            "language": self.language,
            "scraped_at_utc": scraped_at,
        }
