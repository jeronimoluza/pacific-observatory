"""
Spider for Hotline.ua (Ukraine) — hotline.ua

Ukraine's dominant price-comparison portal. Category listings are
server-rendered (Vue SSR, Tier 1A): each `.list-item--row` card carries the
title in `a.item-title` and the lowest aggregated offer price in
`.list-item__value-price` (space/nbsp thousands separator, no decimals).

Because it reports the minimum offer across merchants, the analytical role is
`aggregate_proxy`, not a single retailer SKU. We crawl phone (COICOP 08),
laptop and TV (COICOP 09) categories; classification is deferred to Gemini.

`?p=N` paginates (~49 priced cards/page). product_id is the trailing slug.
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)


class HotlineSpider(scrapy.Spider):
    name = "hotline"
    allowed_domains = ["hotline.ua"]
    currency = "UAH"

    PAGES_PER_CATEGORY = 3
    CATEGORIES = [
        ("mobile/mobilnye-telefony-i-smartfony", "Смартфони"),   # 08
        ("computer/noutbuki", "Ноутбуки"),                       # 09
        ("av/televizory", "Телевізори"),                         # 09
    ]
    _BASE = "https://hotline.ua/ua/{cat}/?p={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    _DIGITS = re.compile(r"\d[\d\s ]*")

    def start_requests(self):
        for cat, title in self.CATEGORIES:
            for page in range(1, self.PAGES_PER_CATEGORY + 1):
                yield scrapy.Request(
                    self._BASE.format(cat=cat, page=page),
                    callback=self.parse_listing,
                    meta={"category": title},
                )

    def parse_listing(self, response):
        cards = response.css("div.list-item--row")
        category = response.meta.get("category")
        logger.info("hotline: %s -> %d cards", response.url, len(cards))
        for card in cards:
            raw = card.css(".list-item__value-price::text").get()
            if not raw:
                continue  # no aggregated offer / out of stock
            m = self._DIGITS.search(raw)
            if not m:
                continue
            price = re.sub(r"[\s ]", "", m.group(0))
            title_a = card.css("a.item-title")
            name = (title_a.css("::text").get() or "").strip()
            href = title_a.css("::attr(href)").get()
            if not name or not price:
                continue
            slug = href.rstrip("/").rsplit("/", 1)[-1] if href else None
            yield {
                "product_id": slug,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": response.urljoin(href) if href else response.url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
