"""
Spider for Deshi10 (Bangladesh, fresh-market/organic grocery) -
https://www.deshi10.com/

Tier 1A, server-rendered HTML (AIZ/6valley-style marketplace theme).
Category listing pages render product cards inline with name + price --
no PDP visit needed. Paginated via `?page=N`; a page with zero product
cards ends that category's crawl. Categories enumerated from /categories
(100 as of 2026-09-01: mostly fresh produce/meat/dairy/grocery, plus a
smaller personal-care tail).
"""

import logging
import re

import scrapy

logger = logging.getLogger(__name__)

_WISHLIST_ID_RE = re.compile(r"addToWishList\((\d+)\)")
MAX_PAGES = 50  # safety cap per category


class Deshi10BdSpider(scrapy.Spider):
    name = "deshi10_bd"
    allowed_domains = ["deshi10.com", "www.deshi10.com"]
    base_url = "https://www.deshi10.com"
    currency = "BDT"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            f"{self.base_url}/categories", callback=self.parse_category_list
        )

    def parse_category_list(self, response):
        hrefs = set(
            response.css("a::attr(href)").re(r"https://www\.deshi10\.com/category/\S+")
        )
        logger.info(f"{self.name}: {len(hrefs)} categories")
        for href in hrefs:
            yield scrapy.Request(
                href,
                callback=self.parse_category_page,
                meta={"page": 1, "category_url": href},
            )

    def parse_category_page(self, response):
        cards = response.css("div.aiz-card-box")
        if not cards:
            return

        for card in cards:
            name = card.css("h3 a::attr(title)").get() or card.css("h3 a::text").get()
            url = card.css("h3 a::attr(href)").get()
            price_texts = [
                p.strip() for p in card.css(".text-primary::text").getall() if p.strip()
            ]
            price_texts = [p for p in price_texts if p.startswith("৳")]
            if not (name and url and price_texts):
                continue

            price_raw = price_texts[-1].replace("৳", "").replace(",", "").strip()
            try:
                price_val = float(price_raw)
            except ValueError:
                continue
            if price_val <= 0:
                continue

            pid_match = _WISHLIST_ID_RE.search(card.get())
            product_id = (
                pid_match.group(1) if pid_match else url.rstrip("/").rsplit("/", 1)[-1]
            )

            yield {
                "product_id": product_id,
                "product_name": name.strip(),
                "price": f"{price_val:.2f}",
                "currency": self.currency,
                "category": None,
                "url": url,
                "scraped_at": response.headers.get("Date", b"").decode("utf-8"),
            }

        page = response.meta["page"]
        if page >= MAX_PAGES:
            return
        next_page = page + 1
        base = response.meta["category_url"]
        yield scrapy.Request(
            f"{base}?page={next_page}",
            callback=self.parse_category_page,
            meta={"page": next_page, "category_url": base},
        )
