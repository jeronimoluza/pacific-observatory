"""
Spider for EVA (Ukraine) — eva.ua

Major UA drugstore / personal-care & cosmetics chain. Category listings are
server-rendered (Nuxt SSR, Tier 1A): cards expose stable `data-testid` hooks
(visible CSS classes are utility-hashed). The current price is in
`[data-testid="product-final-price"]`; `product-price` is the struck-through
old price and must NOT be used.

We crawl cosmetics / perfume / hair & body-care categories -> COICOP 12.1
(personal care). Classification within the division is deferred to Gemini.

`?p=N` paginates (~40 cards/page). product_id is the `prNNNN` token in the URL.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)


class EvaSpider(scrapy.Spider):
    name = "eva"
    allowed_domains = ["eva.ua"]
    currency = "UAH"

    PAGES_PER_CATEGORY = 2  # ~40 cards/page
    CATEGORIES = [
        ("299/kosmetika-dekorativnaja", "Декоративна косметика"),
        ("217/parfjumerija", "Парфумерія"),
        ("024-104/uhod-volosami", "Догляд за волоссям"),
        ("024-273/uhod-licom-telom", "Догляд за обличчям і тілом"),
    ]
    _BASE = "https://eva.ua/ua/{cat}/?p={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    _ID_RE = re.compile(r"/(pr\d+)/")
    _DIGITS = re.compile(r"\d[\d\s ]*")

    def start_requests(self):
        for cat, title in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                yield scrapy.Request(
                    self._BASE.format(cat=cat, page=page),
                    callback=self.parse_listing,
                    meta={"category": title},
                )

    def parse_listing(self, response):
        cards = response.css("div.o-listing-product")
        category = response.meta.get("category")
        logger.info("eva: %s -> %d cards", response.url, len(cards))
        for card in cards:
            raw = card.css('[data-testid="product-final-price"]::text').get()
            if not raw:
                continue
            m = self._DIGITS.search(raw)
            if not m:
                continue
            price = re.sub(r"[\s ]", "", m.group(0))
            title_a = card.css("a.product__title")
            name = (title_a.css("::text").get() or "").strip()
            href = title_a.css("::attr(href)").get()
            if not name or not price:
                continue
            mid = self._ID_RE.search(href or "")
            yield {
                "product_id": mid.group(1) if mid else None,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(href) if href else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
