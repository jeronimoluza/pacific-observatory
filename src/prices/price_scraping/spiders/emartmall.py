"""
Spider for Emart Shopping / emartmall.com.vn (Vietnam) - South Korean E-mart
chain's standalone Vietnamese web storefront (OpenCart, server-rendered HTML).

Category pages are index.php?route=product/category&path=N. N ranges roughly
1-110 (with gaps); each page paginates via &page=M. Product cards use the
`pav_bigmart` OpenCart theme: name in div.name a, price in div.price
(price-new when on sale, else the bare text).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

SELECTORS = {
    "card": "div.product-block",
    "name_link": "div.name a",
    "price_new": "span.price-new",
    "price_box": "div.price",
}

PRODUCT_ID_RE = re.compile(r"product_id=(\d+)")
PRICE_RE = re.compile(r"([\d.,]+)\s*₫")

BASE = (
    "https://emartmall.com.vn/index.php?route=product/category&path={path}&page={page}"
)
MAX_CATEGORY_PATH = 110
MAX_PAGES_PER_CATEGORY = 20


class EmartmallSpider(scrapy.Spider):
    name = "emartmall"
    allowed_domains = ["emartmall.com.vn"]
    currency = "VND"
    language = "vi"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    async def start(self):
        for path in range(1, MAX_CATEGORY_PATH + 1):
            yield scrapy.Request(
                BASE.format(path=path, page=1),
                callback=self.parse_category,
                meta={"path": path, "page": 1},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        page = response.meta["page"]
        cards = response.css(SELECTORS["card"])
        if not cards:
            return

        scraped_at = datetime.now(timezone.utc).isoformat()
        category = (response.css("title::text").get() or "").strip() or None
        yielded = 0
        for card in cards:
            item = self._parse_card(card, category, scraped_at)
            if item:
                yielded += 1
                yield item

        if yielded and page < MAX_PAGES_PER_CATEGORY:
            yield response.follow(
                BASE.format(path=path, page=page + 1),
                callback=self.parse_category,
                meta={"path": path, "page": page + 1},
            )

    def _parse_card(self, card, category, scraped_at):
        href = card.css(f"{SELECTORS['name_link']}::attr(href)").get()
        name = card.css(f"{SELECTORS['name_link']}::text").get()
        if not href or not name or not name.strip():
            return None

        id_match = PRODUCT_ID_RE.search(href)
        product_id = id_match.group(1) if id_match else None

        price_text = card.css(f"{SELECTORS['price_new']}::text").get()
        if not price_text:
            price_texts = card.css(f"{SELECTORS['price_box']}::text").getall()
            price_text = next((t for t in price_texts if PRICE_RE.search(t)), None)
        if not price_text:
            return None
        price_match = PRICE_RE.search(price_text)
        if not price_match:
            return None
        price = price_match.group(1).replace(".", "").replace(",", "")

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
