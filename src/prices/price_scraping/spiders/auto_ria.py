"""
Spider for AUTO.RIA (Ukraine) - auto.ria.com

Used-car classifieds. Server-rendered HTML — listing cards
(`section.ticket-item`) carry the make/model/year as data-attributes and both
USD and UAH prices inline, so no Playwright is needed. We emit the UAH price
for currency consistency.

Whole source maps to COICOP 07.1.2 (second-hand motor cars).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)


class AutoRiaSpider(scrapy.Spider):
    name = "auto_ria"
    allowed_domains = ["auto.ria.com"]
    currency = "UAH"

    PAGES = 5  # ~20 cards/page; pagination is 1-indexed
    _BASE = "https://auto.ria.com/uk/car/used/?page={page}"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "DOWNLOAD_DELAY": 1,
    }

    _PRICE_RE = re.compile(r"[\d\s ]+")

    def start_requests(self):
        urls = list(getattr(self, "start_urls", []) or [])
        if not urls:
            urls = [self._BASE.format(page=p) for p in range(1, self.PAGES + 1)]
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        cards = response.css("section.ticket-item")
        logger.info("auto_ria: %s -> %d cards", response.url, len(cards))
        for card in cards:
            data = card.css("div[data-advertisement-data]")
            pid = card.attrib.get("data-advertisement-id") or data.attrib.get("data-id")

            uah = card.css('div.price-ticket span[data-currency="UAH"]::text').get() or ""
            m = self._PRICE_RE.search(uah)
            price = m.group(0).replace(" ", "").replace(" ", "").strip() if m else ""
            if not price:
                continue  # no UAH-quoted price on this card

            mark = data.attrib.get("data-mark-name")
            model = data.attrib.get("data-model-name")
            year = data.attrib.get("data-year")
            name = " ".join(p for p in (mark, model, year) if p).strip()
            if not name:
                name = card.css("a.address::attr(title)").get()
                name = name.strip() if name else None

            href = card.css("a.m-link-ticket::attr(href), a.address::attr(href)").get()
            url = response.urljoin(href) if href else response.url

            if not name or not price:
                logger.warning("auto_ria: incomplete card at %s", response.url)
                continue

            category = " > ".join(p for p in ("Вживані авто", mark, model) if p)

            yield {
                "product_id": pid,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }
