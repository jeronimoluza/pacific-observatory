"""
Spider for No9 Gibraltar online grocery delivery.

The storefront is ShopWired/ecommercedns-backed and renders product cards with
name, URL, product_id, and price directly in category HTML. Listing extraction
is enough here; PDP visits would add cost without improving the required fields.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import scrapy

logger = logging.getLogger(__name__)


class GibraltarNo9GibraltarSpider(scrapy.Spider):
    name = "gibraltar_no9gibraltar"
    allowed_domains = ["www.no9gibraltar.com", "no9gibraltar.com"]
    currency = "GBP"
    language = "en"

    START_URLS = [
        "https://www.no9gibraltar.com/beers?all=1",
        "https://www.no9gibraltar.com/beers-multipack",
        "https://www.no9gibraltar.com/chocolate?all=1",
        "https://www.no9gibraltar.com/chocolate-multi-deals",
        "https://www.no9gibraltar.com/chocolates",
        "https://www.no9gibraltar.com/crisps-1?all=1",
        "https://www.no9gibraltar.com/crisps-multi-packs",
        "https://www.no9gibraltar.com/energy-bars",
        "https://www.no9gibraltar.com/fresh-meat-available",
        "https://www.no9gibraltar.com/fresh-vegetables",
        "https://www.no9gibraltar.com/frozen-meat",
        "https://www.no9gibraltar.com/dry-goods",
        "https://www.no9gibraltar.com/smoking-and-vapes",
        "https://www.no9gibraltar.com/soft-drinks-1?all=1",
        "https://www.no9gibraltar.com/soft-drinks-bottles",
        "https://www.no9gibraltar.com/soft-drinks",
        "https://www.no9gibraltar.com/cans-multi-pack",
        "https://www.no9gibraltar.com/sprits",
        "https://www.no9gibraltar.com/sunblast",
        "https://www.no9gibraltar.com/tins-and-jars-1?all=1",
        "https://www.no9gibraltar.com/cooking-sauces",
        "https://www.no9gibraltar.com/tins-and-jars",
        "https://www.no9gibraltar.com/water-1?all=1",
        "https://www.no9gibraltar.com/water-bottles",
        "https://www.no9gibraltar.com/water",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 4,
    }

    PRODUCT_ID_RE = re.compile(r"(?:[?&])product_id=(\d+)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen_listing_pages: set[str] = set()
        self.seen_items: set[tuple[str | None, str]] = set()

    async def start(self):
        for url in self.START_URLS:
            yield scrapy.Request(url, callback=self.parse_listing)

    def parse_listing(self, response):
        if response.url in self.seen_listing_pages:
            return
        self.seen_listing_pages.add(response.url)

        category = self._category_name(response)
        cards = response.css("article.product-box")
        logger.info("%s: %s product cards at %s", self.name, len(cards), response.url)
        for card in cards:
            name = self._clean(
                card.css("h3.product-box-heading a::text, h3.item-heading a::text").get()
            )
            url = card.css("h3.product-box-heading a::attr(href), a.image-container::attr(href)").get()
            price = self._price(card)
            product_id = self._product_id(card)
            if not (name and url and price):
                continue

            url = response.urljoin(url)
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
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        for url in self._pagination_urls(response):
            yield scrapy.Request(url, callback=self.parse_listing)

    @classmethod
    def _price(cls, card):
        # Sale price is the current price; the following plain price is the old
        # crossed-out value. Non-sale cards have only one plain price.
        sale = cls._clean(card.css("span.price.sale::text").get())
        if sale:
            return sale
        return cls._clean(card.css("span.price::text").get())

    @classmethod
    def _product_id(cls, card):
        href = card.css("a.js-wishlist-button::attr(href), a.product-wishlist-button::attr(href)").get()
        if not href:
            return None
        match = cls.PRODUCT_ID_RE.search(href)
        return match.group(1) if match else None

    @staticmethod
    def _category_name(response):
        category = response.css("meta[property='og:title']::attr(content)").get()
        if category:
            return " ".join(category.split())
        crumbs = response.css("ul.breadcrumbs li a::text, ul.main-breadcrumbs li a::text").getall()
        crumbs = [" ".join(c.split()) for c in crumbs if c.strip()]
        return " > ".join(crumbs) if crumbs else None

    @classmethod
    def _pagination_urls(cls, response):
        try:
            pages = int(response.css("body::attr(data-pages)").get() or "1")
        except ValueError:
            pages = 1
        if pages <= 1:
            return []
        parsed = urlparse(response.url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        current = int(query.get("page") or "1")
        urls = []
        for page in range(current + 1, pages + 1):
            query["page"] = str(page)
            urls.append(urlunparse(parsed._replace(query=urlencode(query))))
        return urls

    @staticmethod
    def _clean(value):
        if not value:
            return None
        cleaned = value.replace("\xa0", " ").replace("£", "")
        cleaned = " ".join(cleaned.split())
        return cleaned or None

