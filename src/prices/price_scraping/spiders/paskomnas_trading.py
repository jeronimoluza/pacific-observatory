"""
Spider for Paskomnas Trading (Indonesia) - trading.paskomnas.id, the online
storefront of Pasar Induk Osowilangun Surabaya (a wholesale/retail fresh
produce hub run by Paskomnas). carisayur.com 302-redirects here.

Server-rendered HTML product-listing pages at /product?page=N&limit=20 (no
category filter walks the full catalog). Each `.card` element carries the
product name, unit/quantity, price and PDP URL inline - no PDP visits
required. The listing page embeds its own pagination total via a `bootpag`
JS call (`total: N`), which this spider parses from page 1 to generate
requests for the remaining pages.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://trading.paskomnas.id"
_LIMIT = 20

PRICE_RE = re.compile(r"^Rp\s*([0-9][0-9.,]*)$")
ID_RE = re.compile(r"/product/(\d+)-")
TOTAL_PAGES_RE = re.compile(r"total:\s*(\d+)")


class PaskomnasTradingSpider(scrapy.Spider):
    name = "paskomnas_trading"
    allowed_domains = ["trading.paskomnas.id"]
    currency = "IDR"
    language = "id"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1,
    }

    async def start(self):
        yield scrapy.Request(
            f"{_BASE}/product?page=1&limit={_LIMIT}",
            callback=self.parse_listing,
            meta={"page": 1},
        )

    def parse_listing(self, response):
        page = response.meta["page"]

        if page == 1:
            m = TOTAL_PAGES_RE.search(response.text)
            total_pages = int(m.group(1)) if m else 1
            logger.info("paskomnas_trading: total_pages=%d", total_pages)
            for p in range(2, total_pages + 1):
                yield scrapy.Request(
                    f"{_BASE}/product?page={p}&limit={_LIMIT}",
                    callback=self.parse_listing,
                    meta={"page": p},
                )

        scraped_at = datetime.now(timezone.utc).isoformat()
        cards = response.css("div.card")
        yielded = 0
        for card in cards:
            href = card.css(".card-image a::attr(href)").get()
            names = [
                t.strip() for t in card.css(".product-name::text").getall() if t.strip()
            ]
            name = names[0] if names else None
            unit = names[1] if len(names) > 1 else None

            price = None
            price_text = card.css(".product-price.center::text").get() or ""
            m = PRICE_RE.match(price_text.strip())
            if m:
                price = m.group(1).replace(".", "").replace(",", "")

            if not name or not price:
                continue

            product_id = None
            if href:
                pm = ID_RE.search(href)
                product_id = pm.group(1) if pm else None

            yield {
                "product_id": product_id,
                "product_name": f"{name} {unit}".strip() if unit else name,
                "price": price,
                "currency": self.currency,
                "category": None,
                "url": href or response.url,
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
            yielded += 1
        logger.info("paskomnas_trading: page=%d yielded=%d", page, yielded)
