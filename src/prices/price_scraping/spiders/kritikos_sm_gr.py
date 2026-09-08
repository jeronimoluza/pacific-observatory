"""
SUPERMARKET Κρητικός (Kritikos) — https://www.kritikos-sm.gr/.

Server-rendered Next.js storefront (CSS-module class names, but the price
table itself is in the raw HTML — no JS execution needed). Verified live
2026-09-06.

Category seed comes from /sitemap.xml, which lists 158 `/categories/...`
URLs (mix of top-level sections like `/categories/manabikh/` and their
subcategory pages). Each category page server-renders every matching
product in `div.ProductListItem_productItem__*` blocks with product id
(the anchor's `id` attribute, e.g. `pr5b1500...`), name, and final price —
observed returning as many as 140 products on a single top-level category
page with no pagination markup present, so each sitemap URL is fetched
once and not paginated. `category` is taken from the page's own `<h1>`
(one clean top-level label per page; sub-section `<h2>` labels inside a
parent page are not attached per-card to keep this simple, since the URL
list already includes the finer subcategory pages separately and
DuplicationPipeline drops the resulting cross-page duplicates).
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kritikos-sm.gr"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"

_PRICE_RE = re.compile(r"€\s*([\d.,]+)")


class KritikosSmGrSpider(scrapy.Spider):
    name = "kritikos_sm_gr"
    allowed_domains = ["kritikos-sm.gr"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(SITEMAP_URL, callback=self.parse_sitemap, errback=self.errback)

    def parse_sitemap(self, response):
        urls = response.xpath("//*[local-name()='loc']/text()").getall()
        cat_urls = sorted({u for u in urls if "/categories/" in u})
        logger.info(f"{self.name}: category urls found={len(cat_urls)}")
        for url in cat_urls:
            yield response.follow(url, callback=self.parse_listing, errback=self.errback)

    def parse_listing(self, response):
        cards = response.css("div[class^='ProductListItem_productItem']")
        found = 0
        category = response.css("h1::text").get(default="").strip()

        for card in cards:
            product_id = card.css("a::attr(id)").get()
            name = card.css("p[class^='ProductListItem_title__']::text").get()
            href = card.css("a::attr(href)").get()
            price_text = card.css("p[class^='ProductListItem_finalPrice__']::text").get()

            if not name or not href or not price_text:
                continue

            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                continue
            raw = price_match.group(1)
            price_str = raw.replace(".", "").replace(",", ".") if "," in raw else raw
            try:
                price_val = float(price_str)
            except ValueError:
                continue
            if price_val == 0:
                continue

            found += 1
            yield {
                "product_id": product_id or href.rstrip("/").rsplit("/", 1)[-1],
                "product_name": name.strip()[:500],
                "category": category,
                "price": str(price_val),
                "currency": self.currency,
                "available": True,
                "url": response.urljoin(href),
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"{self.name}: {response.url} cards={len(cards)} yielded={found}")

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
