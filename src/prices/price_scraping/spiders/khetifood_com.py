"""
Spider for Khetifood — https://khetifood.com/.

Standard OpenCart storefront, server-rendered, route-based category URLs
(`?route=product/category&path=<id>`). Each `div.product-thumb` card
carries the product name, price ("Rs. 270.00"), and PDP URL with a
`product_id` query param -- no JS required.

Verified live 2026-09-06: GET ?route=product/category&path=215 -> 200,
~17 cards incl. "DHUNGRI" (a local dried-fish/condiment item) Rs. 270.00,
"Ghee" (Cow Ghee 500gm) Rs. 650.00. 20 category paths found on the
homepage nav; this spider seeds from the homepage each run rather than a
hardcoded path list, so newly added categories are picked up.

GOTCHA (from candidate brief): small catalogue overall (candidate note
recorded 23 items in "groceries" at check time) -- expect a modest but
real row count across all 20 categories.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_BASE = "https://khetifood.com"

_CARD_RE = re.compile(r'<div class="product-thumb">.*?(?=<div class="product-thumb">|$)', re.S)
_LINK_RE = re.compile(r'route=product/product&path=\d+&product_id=(\d+)"[^>]*>([^<]+)</a>')
_PRICE_RE = re.compile(r'class="price">\s*(?:<span[^>]*>)?\s*Rs\.\s*([\d,]+\.\d{2})')


class KhetifoodComSpider(scrapy.Spider):
    name = "khetifood_com"
    allowed_domains = ["khetifood.com"]
    currency = "NPR"
    language = "en"

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(_BASE + "/", callback=self.parse_home)

    def parse_home(self, response):
        paths = sorted(set(re.findall(r"route=product/category&(?:amp;)?path=(\d+)", response.text)))
        logger.info(f"khetifood_com: {len(paths)} category paths")
        for path in paths:
            yield scrapy.Request(
                f"{_BASE}/index.php?route=product/category&path={path}",
                callback=self.parse_category,
                meta={"path": path},
            )

    def parse_category(self, response):
        path = response.meta["path"]
        cards = _CARD_RE.findall(response.text)
        scraped_at = datetime.now(timezone.utc).isoformat()
        count = 0
        for card in cards:
            link_m = _LINK_RE.search(card)
            price_m = _PRICE_RE.search(card)
            if not link_m or not price_m:
                continue
            pid, name = link_m.groups()
            count += 1
            yield {
                "product_id": pid,
                "product_name": name.strip()[:500],
                "category": path,
                "price": price_m.group(1).replace(",", ""),
                "currency": self.currency,
                "available": True,
                "url": f"{_BASE}/index.php?route=product/product&path={path}&product_id={pid}",
                "language": self.language,
                "scraped_at_utc": scraped_at,
            }
        logger.info(f"khetifood_com: path={path} items={count}")
