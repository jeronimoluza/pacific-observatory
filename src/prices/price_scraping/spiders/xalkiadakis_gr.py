"""
Chalkiadakis — https://xalkiadakis.gr/ (Crete supermarket chain).

Server-rendered Laravel/Livewire storefront (no JS execution needed).
Note the domain used by the candidate list, chalkiadakis.gr, is a dead
1990s-era FrontPage frameset with no online shop; the live catalogue is at
xalkiadakis.gr (no leading "ch"). Verified live 2026-09-06.

Category tree is walked from the homepage, which links ~250
`/category/<slug>` pages. Each category page renders product cards inside
`div.product-card` blocks with server-rendered name, brand and price text
(price already has HTML entities resolved by the parser, no minor-unit
risk). Pagination is `?page=N` (Laravel default, 1-indexed); the page
simply renders zero `div.product-card` blocks once N exceeds the last page
(verified: page 5 of a 175-item category returns the trailing 19 items,
page 6 returns 0 cards at HTTP 200 — no separate "last page" marker needed,
just stop on an empty page).

product_id is not exposed as a data attribute on the card; the numeric
image filename (`https://xalkiadakis.gr/products/<id>_300x300.jpg`) is the
stable per-product id used site-wide, so it is extracted from the image src
instead of inventing one from the URL slug.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

BASE_URL = "https://xalkiadakis.gr"

_IMG_ID_RE = re.compile(r"/products/(\d+)_")
_PRICE_RE = re.compile(r"([\d.,]+)\s*€")


class XalkiadakisGrSpider(scrapy.Spider):
    name = "xalkiadakis_gr"
    allowed_domains = ["xalkiadakis.gr"]
    currency = "EUR"
    language = "el"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(BASE_URL + "/", callback=self.parse_index, errback=self.errback)

    def parse_index(self, response):
        cats = set()
        for href in response.css("a::attr(href)").getall():
            if "/category/" not in href:
                continue
            href = href.split("?")[0]
            cats.add(response.urljoin(href))

        cats = sorted(cats)
        logger.info(f"{self.name}: categories found={len(cats)}")
        for url in cats:
            yield scrapy.Request(url, callback=self.parse_listing, errback=self.errback)

    def parse_listing(self, response):
        cards = response.css("div.product-card")
        found = 0

        category = response.css("h1::text").get(default="").strip()

        for card in cards:
            name = card.css("h5.product-title a.product-title-link::text").get()
            href = card.css("a.product-title-link::attr(href)").get()
            img_src = card.css("img.product-image::attr(src)").get() or ""
            price_text = " ".join(card.css("div.price-margin div.price::text").getall())

            if not name or not href:
                continue

            id_match = _IMG_ID_RE.search(img_src)
            product_id = id_match.group(1) if id_match else href.rstrip("/").rsplit("/", 1)[-1]

            price_match = _PRICE_RE.search(price_text)
            if not price_match:
                continue
            price = price_match.group(1).replace(".", "").replace(",", ".") if "," in price_match.group(1) else price_match.group(1)
            try:
                price_val = float(price)
            except ValueError:
                continue
            if price_val == 0:
                continue

            found += 1
            yield {
                "product_id": str(product_id),
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

        if cards:
            base = response.url.split("?")[0]
            m = re.search(r"[?&]page=(\d+)", response.url)
            next_page = int(m.group(1)) + 1 if m else 2
            yield scrapy.Request(
                f"{base}?page={next_page}",
                callback=self.parse_listing,
                errback=self.errback,
            )

    def errback(self, failure):
        logger.error(
            f"{self.name} request failed: {failure.request.url} — {failure.value!r}"
        )
