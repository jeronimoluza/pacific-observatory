"""Spider for Phumi Kasephal (phumikasephal.com), a Cambodian farm marketplace.

Two public HTML products, both read in English (locale cookie) with KHR prices:

* /market-prices: the daily market price board (~105 price groups, 30 cards
  per page). Each card is a product (or a category "market average", which mixes
  products and is skipped) with a unit, Low / Suggested / High KHR prices and a
  sample count. The board is
  aggregated by the site from its own live marketplace listings
  (source_type "catalog"). ``price`` is the Suggested value (the headline
  price); Low and High go to ``price_min`` / ``price_max``.
* /products: the live marketplace listings (one KHR price per unit each).

The documented REST API lives under /api/, which robots.txt disallows and
which requires a Bearer token, so it is not used.
"""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy


class PhumikasephalKhSpider(scrapy.Spider):
    name = "phumikasephal_kh"
    allowed_domains = ["phumikasephal.com"]
    base_url = "https://phumikasephal.com"
    currency = "KHR"
    language = "en"
    store_name = "Phumi Kasephal"
    cookies = {"phoumika_locale": "en"}

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": False,
        "RETRY_TIMES": 2,
    }

    _num_re = re.compile(r"\d[\d,]*(?:\.\d+)?")
    _unit_re = re.compile(r"\(([^)]+)\)\s*$")

    async def start(self):
        yield self._page("/market-prices", self.parse_board)
        yield self._page("/products", self.parse_listing)

    def _page(self, path, callback):
        return scrapy.Request(
            urljoin(self.base_url, path), callback=callback, cookies=self.cookies
        )

    def _follow_pages(self, response, callback):
        for href in response.css("nav.pagination a::attr(href)").getall():
            if href.endswith("page=1"):  # same as the bare start URL
                continue
            yield response.follow(href, callback=callback, cookies=self.cookies)

    def _num(self, text):
        match = self._num_re.search(text or "")
        return match.group(0).replace(",", "") if match else None

    def _unit(self, label):
        label = " ".join((label or "").split())
        match = self._unit_re.search(label)
        return (match.group(1) if match else label).strip().lower()

    def parse_board(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        updated = response.css(".market-price-summary div:nth-child(2) b::text").get()
        for card in response.css("article.market-price-card"):
            name = " ".join(card.css("header h2::text").get("").split())
            subtitle = " ".join(card.css("header p::text").get("").split())
            category, _, unit_label = subtitle.rpartition(" · ")
            price = self._num(card.css(".market-price-range .average b::text").get())
            if not name or not price or name.endswith("market average"):
                continue
            spans = card.css(".market-price-range > span")
            footer = card.css("footer span::text").getall()
            key = f"{name}|{category}|{unit_label}"
            product_id = "mp-" + hashlib.md5(key.encode()).hexdigest()[:12]
            yield {
                "product_id": product_id,
                "product_name": name,
                "price": price,
                "currency": self.currency,
                "category": category.lower(),
                "unit": self._unit(unit_label),
                "price_min": self._num(spans[0].css("b::text").get()) if spans else None,
                "price_max": self._num(spans[-1].css("b::text").get()) if spans else None,
                "price_usd": self._num(card.css(".market-price-main small::text").get()),
                "n_observations": self._num(footer[1]) if len(footer) > 1 else None,
                "source_date_label": card.css("footer time::text").get(),
                "city": footer[0].rpartition(" · ")[2] if footer else None,
                "details": {
                    "record_type": "market_price_board",
                    "price_basis": "suggested",
                    "unit_label": unit_label,
                    "board_source": card.css(".market-source::text").get(),
                    "market": footer[0] if footer else None,
                    "board_updated_local": updated,
                },
                "url": f"{self.base_url}/market-prices#{product_id}",
                "language": self.language,
                "store": self.store_name,
                "scraped_at_utc": scraped_at,
            }
        yield from self._follow_pages(response, self.parse_board)

    def parse_listing(self, response):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for card in response.css("article.product-card"):
            href = card.css("a.product-card-v4-title::attr(href)").get()
            name = card.css("a.product-card-v4-title::text").get()
            price = self._num(card.css(".product-card-v4-price b::text").get())
            if not href or not name or not name.strip() or not price:
                continue
            unit_label = card.css(".product-card-v4-price small::text").get("")
            yield {
                "product_id": href.rstrip("/").rsplit("/", 1)[-1],
                "product_name": " ".join(name.split()),
                "price": price,
                "currency": self.currency,
                "category": card.css(".product-card-v4-category b::text").get("").strip().lower(),
                "unit": self._unit(unit_label.lstrip("/")),
                "price_usd": self._num(card.css(".product-card-v4-price-row em::text").get()),
                "details": {
                    "record_type": "marketplace_listing",
                    "unit_label": " ".join(unit_label.lstrip("/").split()),
                    "seller": card.css("a.product-card-v4-store > span:last-of-type::text")
                    .get("")
                    .strip()
                    or None,
                    "stock": card.css(".product-card-v4-meta .is-available::text").get(),
                },
                "url": urljoin(self.base_url, href),
                "language": self.language,
                "store": self.store_name,
                "scraped_at_utc": scraped_at,
            }
        yield from self._follow_pages(response, self.parse_listing)
