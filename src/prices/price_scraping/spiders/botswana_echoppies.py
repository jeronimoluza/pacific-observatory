"""
Spider for eChoppies Botswana online supermarket.

The storefront renders the first category page as HTML and loads subsequent
pages through an ``appendPaging`` POST to ``index.php``. Both responses use the
same ``div.itemBox`` product card markup, so PDP visits are unnecessary for the
core price fields.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import scrapy

logger = logging.getLogger(__name__)


class BotswanaEchoppiesSpider(scrapy.Spider):
    name = "botswana_echoppies"
    allowed_domains = ["echoppies.com", "www.echoppies.com"]
    currency = "BWP"
    language = "en"

    CATEGORY_SEEDS = [
        ("m_beverages", "BEVERAGES"),
        ("m_edible groceries", "EDIBLE GROCERIES"),
        ("b_cfc", "CFC"),
        ("m_ethnic products", "ETHNIC PRODUCTS"),
        ("m_fresh", "FRESH"),
        ("m_perishable", "PERISHABLE"),
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
    }

    CARD_ID_RE = re.compile(r"productImageWrapID_(\d+)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_items: set[tuple[str | None, str]] = set()

    async def start(self):
        for slug, label in self.CATEGORY_SEEDS:
            yield scrapy.Request(
                self._category_url(slug),
                callback=self.parse_listing,
                meta={"category_slug": slug, "category": label},
            )

    def parse_listing(self, response):
        category_slug = response.meta["category_slug"]
        category = response.meta["category"]
        cards = response.css("div.itemBox")
        logger.info("%s: %s product cards at %s", self.name, len(cards), response.url)
        yield from self._items_from_cards(cards, response, category, category_slug)

        total_pages = self._total_pages(response)
        for page in range(2, total_pages + 1):
            yield scrapy.FormRequest(
                "https://echoppies.com/index.php",
                formdata={
                    "event": "appendPaging",
                    "page": str(page),
                    "cat": category_slug,
                    "subcat": "",
                    "botcat": "",
                    "brand": "",
                    "strSortBy": "relavance",
                },
                callback=self.parse_listing_page,
                meta={
                    "category_slug": category_slug,
                    "category": category,
                    "page": page,
                },
                dont_filter=True,
            )

    def parse_listing_page(self, response):
        category = response.meta["category"]
        page = response.meta["page"]
        cards = response.css("div.itemBox")
        logger.info(
            "%s: %s product cards on %s page %s",
            self.name,
            len(cards),
            category,
            page,
        )
        yield from self._items_from_cards(cards, response, category, response.meta["category_slug"])

    def _items_from_cards(self, cards, response, category, category_slug):
        for card in cards:
            name = self._clean(card.css("h5[id^='productNameWrapID_']::text").get())
            url = card.css("a[id^='productImageWrapID_']::attr(href)").get()
            price = self._clean(card.css("span[id^='productPriceWrapID_']::text").get())
            product_id = self._product_id(card)
            product_version = self._product_version(card)
            stock_text = self._clean(" ".join(card.css(".availabilityInfo ::text").getall()))
            if not (name and url and price):
                continue

            url = self._ensure_category_param(response.urljoin(url), category_slug)
            key = (product_id, url)
            if key in self.seen_items:
                continue
            self.seen_items.add(key)
            yield {
                "product_id": product_id or url,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": url,
                "language": self.language,
                "availability": stock_text,
                "source_product_version": product_version,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

    @classmethod
    def _product_id(cls, card):
        anchor_id = card.css("a[id^='productImageWrapID_']::attr(id)").get()
        if not anchor_id:
            return None
        match = cls.CARD_ID_RE.search(anchor_id)
        return match.group(1) if match else None

    @classmethod
    def _product_version(cls, card):
        return cls._clean(card.css("div[id^='productVersionID_']::text").get())

    @staticmethod
    def _total_pages(response):
        value = response.css("input#totalPages::attr(value)").get()
        try:
            return max(1, int(value or "1"))
        except ValueError:
            return 1

    @staticmethod
    def _category_url(slug):
        return "https://echoppies.com/index.php?" + urlencode({"cat": slug})

    @staticmethod
    def _ensure_category_param(url, category):
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if "cat" not in query:
            query["cat"] = category.lower()
        return urlunparse(parsed._replace(query=urlencode(query)))

    @staticmethod
    def _clean(value):
        if not value:
            return None
        cleaned = value.replace("\xa0", " ")
        cleaned = " ".join(cleaned.split())
        return cleaned or None
