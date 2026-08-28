"""
Spider for Shopping China (Paraguay) -- https://www.shoppingchina.com.py/.

Server-rendered HTML with Alpine.js for interactivity (not a client-only
SPA). The homepage's raw HTML has unrendered Alpine template artifacts, but
individual product pages are fully server-rendered -- the price is baked
directly into the page as a plain `price: N,` literal inside an Alpine
x-data JSON block (Alpine hydrates from data already present in the HTML,
unlike Angular/React SPAs).

Catalog is enumerated from the site's own sitemap.xml (5MB, 30243 URLs
live-checked 2026-08-17; 29563 match /producto/<slug>-<id>), which is a far
larger and more reliable surface than any single category page walk.
"""

import logging
import re
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)

_SITEMAP = "https://www.shoppingchina.com.py/sitemap.xml"
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_PRODUCT_RE = re.compile(r"/producto/([a-z0-9-]+)-(\d+)$")
_PRICE_RE = re.compile(r"\bprice:\s*([0-9]+(?:\.[0-9]+)?),")
_H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")


class ShoppingchinaPySpider(scrapy.Spider):
    name = "shoppingchina_py"
    allowed_domains = ["shoppingchina.com.py", "www.shoppingchina.com.py"]
    currency = "PYG"
    language = "es"

    custom_settings = {
        "IMPERSONATE_BROWSERS": ["chrome124"],
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "CONCURRENT_REQUESTS": 8,
        "DOWNLOAD_DELAY": 0.5,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
    }

    async def start(self):
        yield scrapy.Request(
            _SITEMAP, callback=self.parse_sitemap, meta={"impersonate": "chrome124"}
        )

    def parse_sitemap(self, response):
        urls = [
            loc for loc in _LOC_RE.findall(response.text) if _PRODUCT_RE.search(loc)
        ]
        logger.info(f"shoppingchina_py: {len(urls)} product URLs in sitemap")
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_product,
                meta={"impersonate": "chrome124"},
            )

    def parse_product(self, response):
        m = _PRODUCT_RE.search(response.url)
        if not m:
            return
        product_id = m.group(2)
        price_m = _PRICE_RE.search(response.text)
        name_m = _H1_RE.search(response.text)
        if not price_m or not name_m:
            return
        name = name_m.group(1).strip()
        yield {
            "product_id": product_id,
            "product_name": name[:500],
            "category": None,
            "price": price_m.group(1),
            "currency": self.currency,
            "available": True,
            "url": response.url,
            "language": self.language,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }
