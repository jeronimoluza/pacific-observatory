"""
Spider for Zdravica (Ukraine) — zdravica.ua

Online pharmacy. Category listings are server-rendered HTML (Tier 1A) — each
`.product-card` carries a numeric price in `.price-value`, so no Playwright is
needed. Product names are detailed free text spanning pharmaceuticals,
vitamins, medical devices and personal-care, so COICOP (division 06, with some
05.6/12.x spillover) is left to the downstream Gemini classifier.

`?page=N` paginates (45 cards/page). product_id is the `data-product` attribute.
"""

import logging

import scrapy

logger = logging.getLogger(__name__)


class ZdravicaSpider(scrapy.Spider):
    name = "zdravica"
    allowed_domains = ["zdravica.ua"]
    currency = "UAH"

    PAGES_PER_CATEGORY = 2  # 45 cards/page
    # Representative spread across the pharmacy basket (COICOP 06).
    CATEGORIES = [
        "vitamini",
        "analgetiki",
        "antibiotiki",
        "antiseptiki",
        "protizapalni-zasobi",
        "zasobi-vid-zastudi-i-grupu",
        "vitamini-dlja-ditejj",
        "zasobi-dlja-travlennja",
    ]
    _BASE = "https://zdravica.ua/{cat}?page={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    def start_requests(self):
        for cat in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                yield scrapy.Request(
                    self._BASE.format(cat=cat, page=page),
                    callback=self.parse_listing,
                    meta={"category": cat},
                )

    def parse_listing(self, response):
        cards = response.css("div.product-card:not(.empty)")
        category = response.meta.get("category")
        logger.info("zdravica: %s -> %d cards", response.url, len(cards))
        for card in cards:
            price = (card.css("span.price-value::text").get() or "").strip()
            if not price:
                continue  # out-of-stock cards omit the price
            name_a = card.css("a.product-title")
            name = (name_a.css("::text").get() or "").strip()
            href = name_a.css("::attr(href)").get()
            if not name:
                continue
            yield {
                "product_id": card.attrib.get("data-product"),
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": href,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
