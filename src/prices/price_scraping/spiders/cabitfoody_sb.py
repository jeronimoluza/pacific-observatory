"""
Spider for CAB'IT Foody (Solomon Islands) -- take.app/cabitfoody

CAB'IT's second, larger take.app storefront (sibling of cabitonlineshop_sb,
~300 SKUs vs ~40). Same shared take.app platform pattern -- see
cabitonlineshop_sb.py's docstring for the full platform-fingerprint writeup
(server-rendered category listing pages carry product cards directly, no
Playwright/API needed). Kept as an independent spider file rather than a
shared take.app base module per onboarding parallel-safety rules (another
agent may be independently scaffolding a Brunei take.app storefront in the
same window).
"""

import html as html_lib
import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_ALT_RE = re.compile(r'alt="([^"]*)"')
_PRICE_RE = re.compile(r"\$([\d,]+\.\d{2})")


class CabitfoodySbSpider(scrapy.Spider):
    name = "cabitfoody_sb"
    allowed_domains = ["take.app"]
    currency = "SBD"
    language = "en"
    STORE_ALIAS = "cabitfoody"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "RETRY_TIMES": 3,
    }

    async def start(self):
        yield scrapy.Request(
            f"https://take.app/{self.STORE_ALIAS}", callback=self.parse
        )

    def parse(self, response):
        cat_ids = sorted(
            set(
                re.findall(
                    rf"https://take\.app/{self.STORE_ALIAS}/c/([a-zA-Z0-9]+)",
                    response.text,
                )
            )
        )
        logger.info(f"{self.name}: found {len(cat_ids)} categories")
        for cid in cat_ids:
            yield scrapy.Request(
                f"https://take.app/{self.STORE_ALIAS}/c/{cid}",
                callback=self.parse_category,
            )

    def parse_category(self, response):
        title = response.css("title::text").get() or ""
        category = title.split(" - ")[0].strip() or None

        seen_ids: set[str] = set()
        cards = response.css(f'a[href*="/{self.STORE_ALIAS}/p/"]')
        for card in cards:
            href = card.attrib.get("href", "")
            product_id = href.rstrip("/").rsplit("/", 1)[-1]
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)

            outer = card.get()
            alt_m = _ALT_RE.search(outer)
            price_m = _PRICE_RE.search(outer)
            if not (alt_m and price_m):
                continue

            product_name = html_lib.unescape(alt_m.group(1)).strip()
            price = price_m.group(1).replace(",", "")
            if not product_name or not price:
                continue

            yield {
                "product_id": product_id,
                "product_name": product_name,
                "price": price,
                "currency": self.currency,
                "category": category,
                "url": href,
                "language": self.language,
                "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            logger.info(f"Scraped product: {product_name}")
