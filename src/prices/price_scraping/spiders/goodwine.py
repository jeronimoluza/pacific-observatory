"""
Spider for GoodWine (Ukraine) — goodwine.com.ua

Premium wine & spirits retailer. The category listings are server-rendered
Magento HTML (Tier 1A) — product cards carry the final price in a
`data-price-amount` attribute, so no Playwright is needed. We crawl the
alcoholic-beverage categories under /ua/napoi/, which map to COICOP 02.1.

`?p=N` paginates (24 cards/page). product_id is the SKU code in the trailing
URL segment (e.g. .../troja-t2467/ -> t2467).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)


class GoodwineSpider(scrapy.Spider):
    name = "goodwine"
    allowed_domains = ["goodwine.com.ua"]
    currency = "UAH"

    PAGES_PER_CATEGORY = 3  # 24 cards/page
    # Alcoholic-beverage categories (COICOP 02.1). bezalkogol-ni (soft drinks)
    # is intentionally excluded — that's COICOP 01.2, classified elsewhere.
    CATEGORIES = [
        ("vino", "Вино"),
        ("igriste", "Ігристе"),
        ("micni", "Міцні напої"),
        ("viski", "Віскі"),
        ("pivo", "Пиво"),
        ("sidri", "Сидри"),
        ("slaboalkogol-ni-napoi", "Слабоалкогольні"),
    ]
    _BASE = "https://goodwine.com.ua/ua/napoi/{cat}/?p={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    _ID_RE = re.compile(r"-([a-z]?\d+)/?$")

    def start_requests(self):
        for slug, title in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                yield scrapy.Request(
                    self._BASE.format(cat=slug, page=page),
                    callback=self.parse_listing,
                    meta={"category": title},
                )

    def parse_listing(self, response):
        cards = response.css("form.product-item, .product-item-info")
        category = response.meta.get("category")
        logger.info("goodwine: %s -> %d cards", response.url, len(cards))
        for card in cards:
            name_a = card.css("a.product-item-name")
            name = (name_a.css("::text").get() or "").strip()
            href = name_a.css("::attr(href)").get()
            if not name or not href:
                continue

            # Final price lives on the price-wrapper as a numeric data attr.
            amount = card.css(
                'span.price-wrapper[data-price-type="finalPrice"]::attr(data-price-amount)'
            ).get() or card.css("span.price-wrapper::attr(data-price-amount)").get()
            if not amount:
                continue

            m = self._ID_RE.search(href)
            pid = m.group(1) if m else href.rstrip("/").rsplit("/", 1)[-1]

            yield {
                "product_id": pid,
                "product_name": name,
                "price": amount.strip(),
                "currency": self.currency,
                "category": category,
                "url": href,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
